INCREMENT_USAGE_SCRIPT = """
local key = KEYS[1]
local user_id = ARGV[1]
local ip_address = ARGV[2]
local rate_limit = tonumber(ARGV[3])
local current_time = ARGV[4]

if not key or key == '' then
    return {err="Key is required"}
end
if not user_id or user_id == '' then
    return {err="User ID is required"}
end
if not ip_address or ip_address == '' then
    return {err="IP address is required"}
end
if not rate_limit or rate_limit < 0 then
    return {err="Valid rate limit is required"}
end

local user_exists = redis.call("EXISTS", key)

if user_exists == 1 then
    local requests_today = tonumber(redis.call("HGET", key, "requests_today")) or 0
    local remaining = tonumber(redis.call("HGET", key, "remaining_requests")) or rate_limit
    local new_remaining = math.max(0, remaining - 1)

    local updates = {
        "id", tostring(user_id),
        "requests_today", tostring(requests_today + 1),
        "remaining_requests", tostring(new_remaining),
        "last_request", current_time,
        "ip_address", ip_address
    }

    local user_type = redis.call("HGET", key, "tier")
    if not user_type then
        table.insert(updates, "tier")
        table.insert(updates, "unauthenticated")
    end

    redis.call("HMSET", key, unpack(updates))
    redis.call("EXPIRE", key, 86400)
else
    local initial_data = {
        "id", tostring(user_id),
        "ip_address", ip_address,
        "tier", "unauthenticated",
        "requests_today", "1",
        "remaining_requests", tostring(rate_limit - 1),
        "last_request", current_time,
        "last_reset", current_time
    }

    redis.call("HMSET", key, unpack(initial_data))
    redis.call("EXPIRE", key, 86400)
end

local function list_to_table(list)
    local result = {}
    for i = 1, #list, 2 do
        result[list[i]] = list[i + 1]
    end
    return result
end

local data = redis.call("HGETALL", key)
return list_to_table(data)
"""

GET_ALL_USER_DATA_SCRIPT = """
local function get_all_user_data()
    local result = {}
    local cursor = "0"
    local pattern = "user_data:*"

    repeat
        local scan_result = redis.call("SCAN", cursor, "MATCH", pattern, "COUNT", 100)
        cursor = scan_result[1]
        local keys = scan_result[2]

        for _, key in ipairs(keys) do
            local user_id = string.match(key, "user_data:(.+)")
            if user_id then
                local data = redis.call("HGETALL", key)
                if #data > 0 then
                    local user_entry = {"user_data", user_id}
                    for i = 1, #data, 2 do
                        table.insert(user_entry, {data[i], data[i + 1]})
                    end
                    table.insert(result, user_entry)
                end
            end
        end
    until cursor == "0"

    cursor = "0"
    pattern = "ip:*"

    repeat
        local scan_result = redis.call("SCAN", cursor, "MATCH", pattern, "COUNT", 100)
        cursor = scan_result[1]
        local keys = scan_result[2]

        for _, key in ipairs(keys) do
            local ip = string.match(key, "ip:(.+)")
            if ip then
                local data = redis.call("HGETALL", key)
                if #data > 0 then
                    local ip_entry = {"ip", ip}
                    for i = 1, #data, 2 do
                        table.insert(ip_entry, {data[i], data[i + 1]})
                    end
                    table.insert(result, ip_entry)
                end
            end
        end
    until cursor == "0"

    return result
end

return get_all_user_data()
"""

RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local current_time = tonumber(redis.call('TIME')[1])

if not key or key == '' then
    return redis.error_reply("Key is required")
end
if not window or window <= 0 then
    return redis.error_reply("Valid window period is required")
end
if not limit or limit <= 0 then
    return redis.error_reply("Valid limit is required")
end

local cleanup_before = current_time - window
local keys_to_del = {}
local cursor = "0"
local batch_size = 100

repeat
    local scan_result = redis.call("HSCAN", key, cursor, "COUNT", batch_size)
    cursor = scan_result[1]
    local pairs = scan_result[2]

    for i = 1, #pairs, 2 do
        local timestamp = tonumber(pairs[i])
        if timestamp and timestamp < cleanup_before then
            table.insert(keys_to_del, pairs[i])
        end
    end

    if #keys_to_del >= batch_size then
        redis.call("HDEL", key, unpack(keys_to_del))
        keys_to_del = {}
    end
until cursor == "0"

if #keys_to_del > 0 then
    redis.call("HDEL", key, unpack(keys_to_del))
end

local current_field = tostring(current_time)
local window_count = redis.call("HINCRBY", key, current_field, 1)

if window_count == 1 then
    redis.call("EXPIRE", key, window)
end

return window_count <= limit and window_count or -1
"""
