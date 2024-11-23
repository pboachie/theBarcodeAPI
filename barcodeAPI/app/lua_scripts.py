# lua_scripts.py

INCREMENT_USAGE_SCRIPT = """
local key = KEYS[1]
local user_id = ARGV[1]
local ip_address = ARGV[2]
local rate_limit = tonumber(ARGV[3])
local current_time = ARGV[4]

-- Input validation
if not key or key == '' then
    return redis.error_reply("Key is required")
end
if not user_id or user_id == '' then
    return redis.error_reply("User ID is required")
end
if not ip_address or ip_address == '' then
    return redis.error_reply("IP address is required")
end
if not rate_limit or rate_limit < 0 then
    return redis.error_reply("Valid rate limit is required")
end

-- Check if we have user data for this key
local user_exists = redis.call("EXISTS", key)
local result = {}

if user_exists == 1 then
    -- Get current values with proper type conversion
    local requests_today = tonumber(redis.call("HGET", key, "requests_today")) or 0
    local remaining = tonumber(redis.call("HGET", key, "remaining_requests")) or rate_limit
    local new_remaining = math.max(0, remaining - 1)

    -- Prepare updates with type safety
    local updates = {
        "id", tostring(user_id),
        "requests_today", tostring(requests_today + 1),
        "remaining_requests", tostring(new_remaining),
        "last_request", current_time,
        "ip_address", ip_address
    }

    -- Preserve existing tier or set default
    local user_type = redis.call("HGET", key, "tier")
    if not user_type then
        table.insert(updates, "tier")
        table.insert(updates, "unauthenticated")
    end

    -- Atomic update
    redis.call("HMSET", key, unpack(updates))
    redis.call("EXPIRE", key, 86400)
    result = redis.call("HGETALL", key)
else
    -- Initialize new user data with proper type conversion
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
    result = redis.call("HGETALL", key)
end

return result
"""

RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local current_time = tonumber(redis.call('TIME')[1])

-- Input validation
if not key or key == '' then
    return redis.error_reply("Key is required")
end
if not window or window <= 0 then
    return redis.error_reply("Valid window period is required")
end
if not limit or limit <= 0 then
    return redis.error_reply("Valid limit is required")
end

-- Clean up old entries more efficiently
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

    -- Process deletions in batches
    if #keys_to_del >= batch_size then
        redis.call("HDEL", key, unpack(keys_to_del))
        keys_to_del = {}
    end
until cursor == "0"

-- Delete any remaining old entries
if #keys_to_del > 0 then
    redis.call("HDEL", key, unpack(keys_to_del))
end

-- Update current window count
local current_field = tostring(current_time)
local window_count = redis.call("HINCRBY", key, current_field, 1)

-- Set expiration on first hit
if window_count == 1 then
    redis.call("EXPIRE", key, window)
end

return window_count <= limit and window_count or -1
"""
