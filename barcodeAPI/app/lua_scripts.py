# lua_scripts.py


# Script to increment the usage of a user or client, updating the remaining requests and requests today
INCREMENT_USAGE_SCRIPT = """
local user_id = ARGV[1]
local ip_address = ARGV[2]
local rate_limit = tonumber(ARGV[3])
local current_time = ARGV[4]

local key = user_id and user_id ~= "-1" and "user_data:" .. user_id or "ip:" .. ip_address
local user_data = redis.call("GET", key)

if user_data then
    local data = cjson.decode(user_data)
    data.requests_today = data.requests_today + 1
    data.remaining_requests = data.remaining_requests - 1
    redis.call("SET", key, cjson.encode(data), "EX", 86400)
    return cjson.encode(data)
else
    local new_user = {
        id = tonumber(user_id) or -1,
        username = "ip:" .. ip_address,
        ip_address = ip_address,
        tier = "unauthenticated",
        remaining_requests = rate_limit - 1,
        requests_today = 1,
        last_reset = current_time
    }
    redis.call("SET", key, cjson.encode(new_user), "EX", 86400)
    return cjson.encode(new_user)
end
"""

# Script to  control the number of requests a user or client can make within a specified time frame, preventing abuse and ensuring fair resource usage
RATE_LIMIT_SCRIPT = """
local current
current = redis.call("INCR", KEYS[1])
if tonumber(current) == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end
if tonumber(current) > tonumber(ARGV[2]) then
    return -1
end
return current
"""

# Script to retrieve all user and client data stored in Redis, including usage statistics and remaining requests
GET_ALL_USER_DATA_SCRIPT = """
local user_keys = redis.call('KEYS', 'user_data:*')
local ip_keys = redis.call('KEYS', 'ip:*')
local all_data = {}

for _, key in ipairs(user_keys) do
    local user_id = string.sub(key, string.len('user_data:') + 1)
    local user_data = redis.call('GET', key)
    table.insert(all_data, {'user', user_id, user_data})
end

for _, key in ipairs(ip_keys) do
    local ip_address = string.sub(key, string.len('ip:') + 1)
    local user_data = redis.call('GET', key)
    table.insert(all_data, {'ip', ip_address, user_data})
end

return all_data
"""