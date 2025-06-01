import traceback
from redis.asyncio import Redis
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import logging
import pytz
import asyncio
import ipaddress
import gc
import time
from json import JSONDecodeError
import json
import base64

from app.config import settings
from app.utils import IDGenerator
from app.schemas import BatchPriority, UserData, RedisConnectionStats
from app.models import User, Usage
from app.batch_processor import MultiLevelBatchProcessor
from .lua_scripts import INCREMENT_USAGE_SCRIPT, GET_ALL_USER_DATA_SCRIPT, RATE_LIMIT_SCRIPT

logger = logging.getLogger(__name__)

from app.barcode_generator import generate_barcode_image, BarcodeGenerationError
from app.schemas import BarcodeRequest, BarcodeFormatEnum, BarcodeImageFormatEnum

class RedisManager:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.increment_usage_sha = None
        self.pending_results = {}
        self.rate_limit_sha = None
        self.get_all_user_data_sha = None
        self.ip_cache = {}
        self.batch_processor = MultiLevelBatchProcessor(self)
        logger.info("Redis manager initialized")

    @asynccontextmanager
    async def get_connection(self):
        conn = await self.redis.connection_pool.get_connection("_")
        if not conn: raise ConnectionError("Failed to get Redis connection from pool")
        try: yield conn
        finally:
            await conn.disconnect()
            self.redis.connection_pool._available_connections.append(conn)

    @asynccontextmanager
    async def get_pipeline(self):
        pipe = self.redis.pipeline()
        try: yield pipe
        finally: await pipe.reset()

    async def load_lua_scripts(self):
        try:
            self.increment_usage_sha = await self.redis.script_load(INCREMENT_USAGE_SCRIPT)
            self.rate_limit_sha = await self.redis.script_load(RATE_LIMIT_SCRIPT)
            self.get_all_user_data_sha = await self.redis.script_load(GET_ALL_USER_DATA_SCRIPT)
            logger.info("Lua scripts loaded successfully.")
        except Exception as ex: logger.error(f"Error loading Lua scripts: {ex}"); raise

    async def start(self):
        logger.info("Starting Redis manager...")
        try:
            await self.cleanup_redis_keys()
            await self.load_lua_scripts()
            if not all([self.increment_usage_sha, self.rate_limit_sha, self.get_all_user_data_sha]):
                raise RuntimeError("Failed to load one or more Lua scripts.")
            await self.batch_processor.start()
            logger.info("Redis manager started successfully.")
        except Exception as e: logger.error(f"Error starting Redis manager: {e}"); raise

    async def stop(self):
        logger.info("Stopping Redis manager...")
        try:
            await self.batch_processor.stop()
            if self.redis:
                await self.redis.close()
                if self.redis.connection_pool:
                    self.redis.connection_pool.disconnect()
            self.ip_cache.clear(); gc.collect()
            logger.info("Redis manager stopped successfully.")
        except Exception as ex: logger.error(f"Error during Redis manager shutdown: {ex}")

    async def _process_generate_barcode(self, items: List[Tuple[Any, str]], pipe, futures: Dict[str, asyncio.Future]):
        logger.debug(f"Processing {len(items)} barcode generation tasks.")
        for item_tuple, internal_id in items:
            task_info = item_tuple[0] if isinstance(item_tuple, tuple) and len(item_tuple) == 1 and isinstance(item_tuple[0], dict) else item_tuple
            if not isinstance(task_info, dict):
                logger.error(f"Skipping invalid task_info: {task_info}"); futures[internal_id].set_exception(TypeError("Invalid task_info")); continue
            job_id, task_id, data, opts = task_info.get('job_id'), task_info.get('task_id'), task_info.get('data'), task_info.get('options', {})
            if not all([job_id, task_id, data]):
                logger.error(f"Missing info in task: j={job_id}, t={task_id}, d={bool(data)}"); futures[internal_id].set_exception(ValueError("Missing task info")); continue

            key_task, key_results, key_job_main = f"job:{job_id}:task:{task_id}", f"job:{job_id}:results", f"job:{job_id}"
            try:
                req_params = {"data":data, "format":opts.get("format","code128"), "width":int(opts.get("width",200)), "height":int(opts.get("height",100)), "image_format":opts.get("image_format","PNG"), **opts}
                valid_req_params = {k:v for k,v in req_params.items() if v is not None and k in BarcodeRequest.model_fields}
                bc_req = BarcodeRequest(**valid_req_params)
                img_data, c_type = await generate_barcode_image(bc_req, bc_req.get_writer_options())
                b64_img = base64.b64encode(img_data).decode() if isinstance(img_data,bytes) else ""
                img_url = f"data:{c_type};base64,{b64_img}" if b64_img else f"/placeholder/{task_id}.{bc_req.image_format.value.lower()}"
                res_dict = {'original_data':data,'output_filename':task_info.get('output_filename'),'status':'Generated','barcode_image_url':img_url,'error_message':None}
                task_upd = {'status':'COMPLETED','result':res_dict,'data':data,'output_filename':task_info.get('output_filename')}
                pipe.set(key_task,json.dumps(task_upd)); pipe.rpush(key_results,json.dumps(res_dict))
                if not futures[internal_id].done(): futures[internal_id].set_result(True)
            except (BarcodeGenerationError, ValueError, TypeError) as ex_inner:
                logger.error(f"Error for task {task_id} in job {job_id}: {ex_inner}")
                err_res = {'original_data':data,'output_filename':task_info.get('output_filename'),'status':'Failed','error_message':str(ex_inner),'barcode_image_url':None}
                task_err_upd = {'status':'FAILED','error':str(ex_inner),'result':err_res,'data':data,'output_filename':task_info.get('output_filename')}
                pipe.set(key_task,json.dumps(task_err_upd)); pipe.rpush(key_results,json.dumps(err_res))
                if not futures[internal_id].done(): futures[internal_id].set_exception(ex_inner)
            finally: pipe.hincrby(key_job_main,"processed_items",1)
        try: await pipe.execute()
        except Exception as r_ex: logger.error(f"Redis exec error in barcode batch: {r_ex}"); [f.set_exception(r_ex) for _,f_id in items if not (f:=futures[f_id]).done()]

    async def _process_add_active_token(self, items: List[Tuple[Any, str]], pipe, futures: Dict[str, asyncio.Future]):
        try:
            for item_tuple, internal_id in items:
                user_id, token, expire_time = item_tuple
                key = f"user_data:{user_id}"
                pipe.hset(key, "active_token", token)
                pipe.expire(key, expire_time)
            results = await pipe.execute() # Expects 2 results per item (HSET, EXPIRE)
            for i, (_, internal_id) in enumerate(items):
                if not futures[internal_id].done(): futures[internal_id].set_result(bool(results[i*2] is not None and results[i*2+1])) # Simplistic success
        except Exception as ex: logger.error(f"Error in _process_add_active_token: {ex}"); [f.set_exception(ex) for _,f_id in items if not (f:=futures[f_id]).done()]

    async def _process_remove_active_token(self, items: List[Tuple[Any, str]], pipe, futures: Dict[str, asyncio.Future]):
        try:
            for item_tuple, internal_id in items: user_id, = item_tuple; pipe.hdel(f"user_data:{user_id}", "active_token")
            results = await pipe.execute() # Expects 1 result per item
            for i, (_, internal_id) in enumerate(items):
                if not futures[internal_id].done(): futures[internal_id].set_result(bool(results[i]))
        except Exception as ex: logger.error(f"Error in _process_remove_active_token: {ex}"); [f.set_exception(ex) for _,f_id in items if not (f:=futures[f_id]).done()]

    async def process_batch_operation(self, operation: str, items: List[Tuple[Any, str]], pipe, pending_results):
        try:
            logger.debug(f"Op: {operation}, items: {len(items)}")
            handlers = {
                "generate_barcode": self._process_generate_barcode, "get_user_data": self._process_get_user_data,
                "set_user_data": self._process_set_user_data, "increment_usage": self._process_increment_usage,
                "check_rate_limit": self._process_check_rate_limit, "is_token_active": self._process_token_checks,
                "get_active_token": self._process_get_tokens, "add_active_token": self._process_add_active_token,
                "remove_active_token": self._process_remove_active_token, "reset_daily_usage": self._process_reset_daily_usage,
                "set_username_mapping": self._process_username_mappings, "get_user_data_by_ip": self._process_get_user_data_by_ip,
            }
            handler = handlers.get(operation)
            if not handler: logger.error(f"Unknown op: {operation}"); [p[1].set_exception(NotImplementedError(f"Op {operation} unknown")) for p in items if not p[1].done()]; return
            await handler(items, pipe, pending_results)
        except Exception as ex:
            logger.error(f"Error in process_batch_operation {operation}: {ex}", exc_info=True)
            for _, item_id in items:
                fut = pending_results.get(item_id)
                if fut and not fut.done(): fut.set_exception(ex) if isinstance(ex, (ValueError,TypeError,NotImplementedError)) else fut.set_result(await self.get_default_value(operation, items[0][0] if items else None))

    async def _process_set_user_data(self, items: List[Tuple[Any, str]], pipe, pending_results):
        try:
            for item_tuple, internal_id in items:
                user_data_dict = item_tuple[0]
                user_data = user_data_dict['user_data']
                if not isinstance(user_data, UserData):
                    if not pending_results[internal_id].done(): pending_results[internal_id].set_result(False); continue
                key = f"user_data:{user_data.id}"
                mapping = {f.name: str(getattr(user_data, f.name)) if getattr(user_data, f.name) is not None else "" for f in UserData.model_fields.values()}
                mapping['last_request'] = user_data.last_request.isoformat() if user_data.last_request else datetime.now(pytz.utc).isoformat()
                mapping['last_reset'] = user_data.last_reset.isoformat() if user_data.last_reset else datetime.now(pytz.utc).isoformat()
                pipe.hset(key, mapping=mapping); pipe.expire(key, 86400)
            results = await pipe.execute()
            for i, (_, internal_id) in enumerate(items):
                if not pending_results[internal_id].done(): pending_results[internal_id].set_result(bool(results[i*2]))
        except Exception as ex: logger.error(f"Err in _process_set_user_data: {ex}"); [f.set_exception(ex) for _,f_id in items if not (f:=pending_results[f_id]).done()]


    async def _process_get_user_data(self, items: List[Tuple[Any, str]], pipe, pending_results):
        try:
            for item_tuple, internal_id in items:
                payload = item_tuple[0]
                user_identifier = payload['user_id']
                key = f"user_data:{user_identifier}"
                if payload.get('is_username_lookup'):
                    logger.debug(f"Username lookup for {user_identifier} - ensure ID is used for HGETALL key.")
                    pass
                pipe.hgetall(key)

            results = await pipe.execute()
            for i, (item_tuple, internal_id) in enumerate(items):
                payload = item_tuple[0]
                ip_address = payload.get('ip_address')
                if not pending_results[internal_id].done():
                    if results[i]:
                        try:
                            user_data_dict = {k.decode(): v.decode() for k, v in results[i].items()}
                            for f in ['req_today','rem_req']: user_data_dict[f]=int(user_data_dict.get(f,0))
                            now=datetime.now(pytz.utc)
                            for f in ['last_req','last_rst']: user_data_dict[f]=datetime.fromisoformat(user_data_dict.get(f, now.isoformat()))
                            user_data_dict.setdefault('id', payload['user_id']); user_data_dict.setdefault('tier','unauthenticated')
                            pending_results[internal_id].set_result(UserData(**user_data_dict))
                        except Exception as e_conv:
                             logger.error(f"Error converting UserData: {e_conv}"); pending_results[internal_id].set_result(await self.create_default_user_data(ip_address) if ip_address else None)
                    else:
                        pending_results[internal_id].set_result(await self.create_default_user_data(ip_address) if ip_address else None)
        except Exception as ex: logger.error(f"Err in _process_get_user_data: {ex}"); [f.set_exception(ex) for _,f_id in items if not (f:=pending_results[f_id]).done()]


    async def set_user_data(self, user_data: UserData) -> bool:
        try:
            return await self.batch_processor.add_to_batch("set_user_data", ({'user_data': user_data},), BatchPriority.MEDIUM) or False
        except Exception as ex: logger.error(f"Error adding set_user_data to batch: {ex}"); return False

    async def get_user_data(self, user_id: Optional[str], ip_address: str) -> UserData:
        try:
            payload = {'user_id': user_id, 'ip_address': ip_address, 'is_username_lookup': False}
            user_data_result = await self.batch_processor.add_to_batch("get_user_data", (payload,), BatchPriority.HIGH)
            return user_data_result if user_data_result else await self.create_default_user_data(ip_address)
        except Exception as ex: logger.error(f"Error in get_user_data batch call: {ex}"); return await self.create_default_user_data(ip_address)

    async def get_user_data_by_ip(self, ip_address: str) -> Optional[UserData]:
        try:
            return await self.batch_processor.add_to_batch("get_user_data_by_ip", (ip_address,), BatchPriority.HIGH)
        except Exception as ex: logger.error(f"Error adding get_user_data_by_ip to batch: {ex}"); return None

    async def increment_usage(self, user_id: Optional[str], ip_address: str) -> UserData:
        try:
            user_data_result = await self.batch_processor.add_to_batch("increment_usage", (user_id, ip_address), BatchPriority.URGENT)
            return user_data_result if user_data_result else await self.create_default_user_data(ip_address)
        except Exception as ex: logger.error(f"Error in increment_usage batch call: {ex}"); return await self.create_default_user_data(ip_address)

    async def check_rate_limit(self, key: str) -> bool:
        try: return await self.batch_processor.add_to_batch("check_rate_limit", (key,), BatchPriority.URGENT) or False
        except Exception as ex: logger.error(f"Error adding check_rate_limit to batch: {ex}"); return False

    async def get_active_token(self, user_id: int) -> Optional[str]:
        try: return await self.batch_processor.add_to_batch("get_active_token", (user_id,), BatchPriority.HIGH)
        except Exception as ex: logger.error(f"Error adding get_active_token to batch: {ex}"); return None

    async def is_token_active(self, user_id: int, token: str) -> bool:
        try: return await self.batch_processor.add_to_batch("is_token_active", (user_id, token), BatchPriority.HIGH) or False
        except Exception as ex: logger.error(f"Error adding is_token_active to batch: {ex}"); return False

    async def add_active_token(self, user_id: int, token: str, expire_time: int = 3600) -> bool:
        try: return await self.batch_processor.add_to_batch("add_active_token", (user_id, token, expire_time), BatchPriority.MEDIUM) or False
        except Exception as ex: logger.error(f"Error adding add_active_token to batch: {ex}"); return False

    async def remove_active_token(self, user_id: int) -> bool:
        try: return await self.batch_processor.add_to_batch("remove_active_token", (user_id,), BatchPriority.MEDIUM) or False
        except Exception as ex: logger.error(f"Error adding remove_active_token to batch: {ex}"); return False

    async def set_username_to_id_mapping(self, username: str, user_id: str) -> bool:
        try: return await self.batch_processor.add_to_batch("set_username_mapping", (username, user_id), BatchPriority.LOW) or False
        except Exception as ex: logger.error(f"Error setting username_to_id_mapping: {ex}"); return False

    async def sync_all_username_mappings(self, db: AsyncSession):
        tasks = []
        try:
            logger.debug("Starting sync_all_username_mappings")
            async with db as session: users = (await session.execute(select(User))).scalars().all()
            logger.debug(f"Retrieved {len(users)} users.")
            for user in users:
                if user.username and user.id:
                    tasks.append(self.batch_processor.add_to_batch("set_username_mapping", (user.username, str(user.id)), BatchPriority.LOW))
            if tasks: await asyncio.gather(*[asyncio.ensure_future(t) for t in tasks if asyncio.iscoroutine(t) or asyncio.isfuture(t)])
            logger.info(f"Username mappings sync tasks ({len(tasks)}) added.")
        except Exception as ex: logger.error(f"Error in sync_all_username_mappings: {ex}", exc_info=True)

    async def sync_db_to_redis(self, db: AsyncSession):
        tasks = []
        logger.debug("Starting sync_db_to_redis process.")
        try:
            async with db as session: db_items = (await session.execute(select(Usage))).scalars().all()
            for item in db_items:
                ud_obj = UserData(id=str(item.user_id), username=getattr(item,'username',f"user_{item.user_id}"), ip_address=str(item.ip_address), tier=item.tier, requests_today=item.requests_today, remaining_requests=item.remaining_requests, last_request=item.last_request, last_reset=item.last_reset)
                tasks.append(self.batch_processor.add_to_batch("set_user_data", ({'user_data': ud_obj},), BatchPriority.LOW))
            if tasks: await asyncio.gather(*[asyncio.ensure_future(t) for t in tasks if asyncio.iscoroutine(t) or asyncio.isfuture(t)])
            logger.info(f"DB to Redis sync tasks ({len(tasks)}) added.")
        except Exception as ex: logger.error(f"Error in sync_db_to_redis: {ex}", exc_info=True)

    def _cleanup_future(self, batch_id: str, result: Any):
        future = self.pending_results.get(batch_id)
        if future and not future.done(): future.set_result(result)

    def _convert_list_to_dict(self, data: List[Any]) -> Dict[bytes, bytes]:
        result = {}
        for i in range(0, len(data), 2):
            key = data[i].encode('utf-8') if isinstance(data[i], str) else data[i]
            value = data[i+1].encode('utf-8') if isinstance(data[i+1], str) else data[i+1]
            result[key] = value
        return result

    def _decode_redis_hash(self, hash_data: Dict[bytes, bytes], defaults: Dict[str, Any]) -> Dict[str, Any]:
        result = {}
        try:
            str_data = {k.decode('utf-8'): v.decode('utf-8') for k, v in hash_data.items()}
            result = defaults.copy()
            for key, value in str_data.items():
                if key in result:
                    value_str = str(value).strip()
                    try:
                        if isinstance(result[key], int): result[key] = int(value_str) if value_str else result[key]
                        elif isinstance(result[key], datetime): result[key] = datetime.fromisoformat(value_str) if value_str else result[key]
                        else: result[key] = value_str if value_str else result[key]
                    except (ValueError, TypeError) as ex: logger.error(f"Error converting {key}={value}: {ex}")
            return result
        except Exception as ex:
            logger.error(f"Error parsing Redis hash: {ex}")
            return defaults

    async def _process_check_rate_limit(self, items: List[Tuple[Any, str]], pipe, pending_results):
        try:
            window = settings.RATE_LIMIT_WINDOW; limit = settings.RATE_LIMIT_LIMIT
            current_time = datetime.now(pytz.utc).isoformat()
            for (key,), batch_id in items: pipe.eval(RATE_LIMIT_SCRIPT, 1, key, window, limit, current_time)
            results = await pipe.execute()
            for i, (_, batch_id) in enumerate(items):
                future = pending_results.get(batch_id)
                if future and not future.done(): future.set_result(results[i] != -1)
        except Exception as ex:
            logger.error(f"Error in _process_check_rate_limit: {ex}")
            for _, batch_id in items:
                future = pending_results.get(batch_id)
                if future and not future.done(): future.set_result(False)

    async def _process_token_checks(self, items: List[Tuple[Any, str]], pipe, pending_results):
        try:
            for item_tuple, internal_id in items:
                user_id, token = item_tuple
                pipe.hget(f"user_data:{user_id}", "active_token")
            results = await pipe.execute()
            for i, ((_, token), internal_id) in enumerate(items):
                future = pending_results.get(internal_id)
                if future and not future.done():
                    stored_token_bytes = results[i]
                    stored_token = stored_token_bytes.decode() if stored_token_bytes else None
                    future.set_result(stored_token == token)
        except Exception as ex:
            logger.error(f"Error in _process_token_checks: {ex}")
            for _, internal_id in items:
                if internal_id in pending_results and not pending_results[internal_id].done():
                    pending_results[internal_id].set_exception(ex)

    async def _process_get_tokens(self, items: List[Tuple[Any, str]], pipe, pending_results):
        try:
            for item_tuple, internal_id in items:
                user_id, = item_tuple
                pipe.hget(f"user_data:{user_id}", "active_token")
            results = await pipe.execute()
            for i, (_, internal_id) in enumerate(items):
                future = pending_results.get(internal_id)
                if future and not future.done():
                    token_bytes = results[i]
                    future.set_result(token_bytes.decode() if token_bytes else None)
        except Exception as ex:
            logger.error(f"Error in _process_get_tokens: {ex}")
            for _, internal_id in items:
                if internal_id in pending_results and not pending_results[internal_id].done():
                    pending_results[internal_id].set_exception(ex)

    async def _process_reset_daily_usage(self, items: List[Tuple[Any, str]], pipe, pending_results):
        try:
            for (key,), batch_id in items:
                key_type = await self.redis.type(key)
                mapping = {"requests_today": "0", "remaining_requests": str(settings.RateLimit.get_limit("unauthenticated"))}
                if key_type == b'hash': pipe.hset(key, mapping=mapping)
                elif key.startswith("ip:") or key.startswith("user_data:"):
                    pipe.hset(key, mapping=mapping); pipe.expire(key, 86400)
                else: logger.warning(f"Invalid key type for {key}, skipping"); continue
            results = await pipe.execute()
            for i, (_, batch_id) in enumerate(items):
                future = pending_results.get(batch_id)
                if future and not future.done(): future.set_result(True)
        except Exception as ex:
            logger.error(f"Error in _process_reset_daily_usage: {ex}")
            for _, batch_id in items:
                future = pending_results.get(batch_id)
                if future and not future.done(): future.set_result(False)

    async def _process_username_mappings(self, items: List[Tuple[Any, str]], pipe, pending_results):
        try:
            for item_tuple, internal_id in items:
                username, user_id = item_tuple
                key = self._get_key(user_id, None)
                pipe.hset(key, "username", username)
            results = await pipe.execute()
            for i, (_, internal_id) in enumerate(items):
                future = pending_results.get(internal_id)
                if future and not future.done(): future.set_result(bool(results[i]))
        except Exception as ex:
            logger.error(f"Error in _process_username_mappings: {ex}")
            for _, internal_id in items:
                if internal_id in pending_results and not pending_results[internal_id].done():
                     pending_results[internal_id].set_exception(ex)

    async def _process_get_user_data_by_ip(self, items: List[Tuple[Any, str]], pipe, pending_results):
        try:
            for (ip_address,), batch_id in items: key = f"ip:{ip_address}"; pipe.hgetall(key)
            results = await pipe.execute()
            for i, ((ip_address,), batch_id) in enumerate(items):
                future = pending_results.get(batch_id)
                if future and not future.done():
                    if results[i]:
                        try:
                            defaults = await self.create_default_user_data(ip_address)
                            user_data_dict = self._decode_redis_hash(results[i], defaults.__dict__)
                            future.set_result(UserData(**user_data_dict))
                        except Exception as ex:
                            logger.error(f"Error processing user data for IP {ip_address}: {ex}")
                            future.set_result(await self.create_default_user_data(ip_address))
                    else: future.set_result(await self.create_default_user_data(ip_address))
        except Exception as ex:
            logger.error(f"Error in _process_get_user_data_by_ip: {ex}")
            for (ip_address,), batch_id in items:
                future = pending_results.get(batch_id)
                if future and not future.done(): future.set_result(await self.create_default_user_data(ip_address))

    def _get_key(self, user_id: Optional[str] = None, ip_address: Optional[str] = None) -> str:
        if user_id is None or user_id == -1:
            ip_str = self.ip_cache.get(ip_address)
            if ip_str is None:
                try:
                    ip = ipaddress.ip_address(ip_address or "")
                    ip_str = ip.compressed
                    if ip_address: self.ip_cache[ip_address] = ip_str
                except ValueError: ip_str = ip_address or "unknown_ip"
            return f"ip:{ip_str}"
        return f"user_data:{user_id}"

    def _extract_ip_address(self, item: Any) -> str:
        if isinstance(item, tuple) and len(item)>0:
            inner_tuple = item[0]
            if len(inner_tuple) > 1 and isinstance(inner_tuple[1], str): return inner_tuple[1]
            if len(inner_tuple) == 1 and isinstance(inner_tuple[0], str): return inner_tuple[0]
        elif isinstance(item, dict): return item.get('ip_address', "unknown")
        return str(item) if item is not None else "unknown"

    async def check_redis(self) -> str:
        try: async with self.get_connection(): await self.redis.ping(); return "ok"
        except Exception as ex: logger.error(f"Redis health check failed: {ex}"); return "error"

    async def get_connection_stats(self) -> RedisConnectionStats:
        try:
            async with self.get_connection():
                info = await self.redis.info("clients")
                return RedisConnectionStats(connected_clients=info.get("connected_clients",0), blocked_clients=info.get("blocked_clients",0), tracking_clients=info.get("tracking_clients",0), total_connections=info.get("total_connections_received",0), in_use_connections=len(self.redis.connection_pool._in_use_connections))
        except Exception as ex: logger.error(f"Error getting connection stats: {ex}"); return RedisConnectionStats(connected_clients=0,blocked_clients=0,tracking_clients=0,total_connections=0,in_use_connections=0)

    async def create_default_user_data(self, ip_address: str) -> UserData:
        try:
            now = datetime.now(pytz.utc)
            user_data = UserData(id=IDGenerator.generate_id(), username=f"ip:{ip_address}", ip_address=ip_address, tier="unauthenticated", remaining_requests=settings.RateLimit.get_limit("unauthenticated"), requests_today=0, last_request=now, last_reset=now)
            key = self._get_key(user_data.id, ip_address)
            ip_key = f"ip:{ip_address}"

            mapping = {f.name: str(getattr(user_data, f.name)) if getattr(user_data, f.name) is not None else "" for f in UserData.model_fields.values()}
            mapping['last_request'] = user_data.last_request.isoformat()
            mapping['last_reset'] = user_data.last_reset.isoformat()

            async with self.redis.pipeline() as pipe:
                pipe.hset(key, mapping=mapping)
                pipe.expire(key, 86400)
                pipe.hset(ip_key, mapping={"id": str(user_data.id), "ip_address": ip_address})
                pipe.expire(ip_key, 86400)
                await pipe.execute()
            return user_data
        except Exception as ex: logger.error(f"Error creating default user data for IP {ip_address}: {ex}", exc_info=True); raise

    async def cleanup_redis_keys(self):
        try:
            ip_keys, user_keys = await self.redis.keys("ip:*"), await self.redis.keys("user_data:*")
            async with self.get_pipeline() as pipe:
                for key_bytes in ip_keys + user_keys:
                    key = key_bytes.decode('utf-8')
                    key_type_bytes = await self.redis.type(key)
                    key_type = key_type_bytes.decode('utf-8')
                    if key_type != 'hash':
                        logger.debug(f"Converting non-hash key: {key} (type: {key_type})")
                        old_data_bytes = await self.redis.get(key)
                        await pipe.delete(key)
                        if old_data_bytes:
                            try:
                                old_data_str = old_data_bytes.decode('utf-8')
                                data = json.loads(old_data_str)
                                if isinstance(data, dict): pipe.hset(key, mapping=data); pipe.expire(key, 86400); logger.debug(f"Converted key {key} to hash")
                            except Exception as e: logger.warning(f"Could not convert data for key {key}: {e}")
                await pipe.execute()
            logger.info("Completed Redis key cleanup.")
        except Exception as ex: logger.error(f"Error during Redis cleanup: {ex}", exc_info=True)

    async def _gather_with_cleanup(self, tasks: List[asyncio.Task]) -> List[Any]:
        try: return await asyncio.gather(*tasks)
        except Exception:
            for task in tasks:
                if not task.done(): task.cancel()
            raise
        finally:
            for task in tasks:
                try:
                    if not task.done(): task.cancel()
                    await task
                except Exception: pass


    async def get_metrics(self) -> dict:
        try:
            info, pool = await self.redis.info(), self.redis.connection_pool
            batch_metrics = { str(prio): {"queue_size": len(proc.operations), "processing": proc.processing, "interval_ms": int(proc.interval*1000)} for prio, proc in self.batch_processor.processors.items()}
            return {
                "redis": {"connected_clients": info.get("connected_clients",0), "used_memory_human": info.get("used_memory_human","0"), "total_connections_received": info.get("total_connections_received",0), "total_commands_processed": info.get("total_commands_processed",0)},
                "connection_pool": {"max_connections": pool.max_connections, "in_use_connections": len(pool._in_use_connections), "available_connections": len(pool._available_connections), "total_connections": len(pool._in_use_connections) + len(pool._available_connections)},
                "batch_processors": batch_metrics
            }
        except Exception as ex: logger.error(f"Error getting metrics: {ex}"); return {"error":str(ex), "redis":{},"connection_pool":{},"batch_processors":{}}

    async def get_user_data_by_username(self, username: str) -> Optional[UserData]:
        _batch_response_for_cleanup = None
        try:
            item_payload = ({'user_id': username, 'is_username_lookup': True},)
            batch_response = await self.batch_processor.add_to_batch(
                "get_user_data",
                item_payload,
                priority=BatchPriority.HIGH
            )
            _batch_response_for_cleanup = batch_response

            if not batch_response:
                logger.warning(f"No data found for username: {username}")
                return None
            if isinstance(batch_response, UserData):
                return batch_response

            if isinstance(batch_response, dict):
                logger.warning(f"get_user_data_by_username received dict, expected UserData. Attempting conversion for {username}.")
                try:
                    required_fields = UserData.model_fields.keys()
                    if all(field in batch_response for field in required_fields):
                        for field in ['requests_today', 'remaining_requests']:
                            if field in batch_response and batch_response[field] is not None: batch_response[field] = int(batch_response[field])
                            else: batch_response[field] = 0
                        for field in ['last_request', 'last_reset']:
                            if field in batch_response and isinstance(batch_response[field], str):
                                batch_response[field] = datetime.fromisoformat(batch_response[field])
                            elif field not in batch_response or batch_response[field] is None :
                                batch_response[field] = datetime.now(pytz.utc)
                        return UserData(**batch_response)
                    else:
                        logger.error(f"Missing required fields in dict response for username {username}: {batch_response}")
                        return None
                except Exception as e_conv:
                    logger.error(f"Error converting dict to UserData for username {username}: {e_conv}")
                    return None

            logger.error(f"Unexpected response type for username {username}: {type(batch_response)}")
            return None
        except Exception as ex:
            logger.error(f"Error getting user data by username {username}: {str(ex)}")
            return None
        finally:
            pending_results_for_cleanup = {"get_user_data": [_batch_response_for_cleanup]} if _batch_response_for_cleanup is not None else {}
            if hasattr(self.batch_processor, '_cleanup_pending_results'):
                 await self.batch_processor._cleanup_pending_results(pending_results_for_cleanup)
            else:
                logger.warning("_cleanup_pending_results method not found on batch_processor. Skipping cleanup.")

    async def sync_redis_to_db(self, db: AsyncSession):
        logger.debug("Starting sync_redis_to_db process.")
        try:
            all_user_data = await self.redis.evalsha(self.get_all_user_data_sha, 0)
            logger.debug(f"Retrieved {len(all_user_data)} records from Redis.")
            user_records, usage_records = {}, {}
            for entry in all_user_data:
                try:
                    if not entry or len(entry) < 2: continue
                    entry_type, identifier = entry[0], entry[1]
                    if not identifier: continue
                    data_dict = {k.decode('utf-8'):v.decode('utf-8') for k,v in (fd for fd in entry[2:] if isinstance(fd, (list,tuple)) and len(fd)==2)}
                    if not data_dict: continue
                    now = datetime.now(pytz.utc)
                    if entry_type == b"user_data":
                        user_id = identifier.decode('utf-8')
                        user_records[user_id] = {
                            'id': user_id, 'username': data_dict.get('username', f"user_{user_id}"),
                            'tier': data_dict.get('tier', 'unauthenticated'), 'ip_address': data_dict.get('ip_address'),
                            'requests_today': int(data_dict.get('requests_today',0)),
                            'remaining_requests': int(data_dict.get('remaining_requests', settings.RateLimit.get_limit("unauthenticated"))),
                            'last_request': datetime.fromisoformat(data_dict.get('last_request', now.isoformat())),
                            'hashed_password': data_dict.get('hashed_password'),
                        }
                        usage_records[user_id] = {
                            'user_id': user_id, 'ip_address': data_dict.get('ip_address'),
                            'requests_today': int(data_dict.get('requests_today',0)),
                            'remaining_requests': int(data_dict.get('remaining_requests', settings.RateLimit.get_limit("unauthenticated"))),
                            'last_reset': datetime.fromisoformat(data_dict.get('last_reset', now.isoformat())),
                            'last_request': datetime.fromisoformat(data_dict.get('last_request', now.isoformat())),
                            'tier': data_dict.get('tier', 'unauthenticated'),
                        }
                except Exception as ex: logger.error(f"Error processing entry {entry}: {ex}"); continue
            if user_records:
                stmt = insert(User).values(list(user_records.values()))
                set_clause = {c.name: getattr(stmt.excluded, c.name) for c in User.__table__.columns if c.name != 'id'}
                stmt = stmt.on_conflict_do_update(index_elements=['id'], set_=set_clause)
                await db.execute(stmt)
            if usage_records:
                stmt = insert(Usage).values(list(usage_records.values()))
                set_clause_usage = {c.name: getattr(stmt.excluded, c.name) for c in Usage.__table__.columns if c.name != 'user_id'}
                stmt = stmt.on_conflict_do_update(index_elements=["user_id"], set_=set_clause_usage)
                await db.execute(stmt)
            await db.commit()
            logger.info(f"Synced {len(user_records)} users and {len(usage_records)} usages successfully.")
        except Exception as ex: logger.error(f"Error syncing Redis data to database: {str(ex)}", exc_info=True); raise
        finally: await db.close()

