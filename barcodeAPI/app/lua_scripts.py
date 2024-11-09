# lua_scripts.py

# Script to increment the usage of a user or client, updating remaining requests and today's usage count
INCREMENT_USAGE_SCRIPT = """
local user_id = ARGV[1]
local ip_address = ARGV[2]
local rate_limit = tonumber(ARGV[3])
local current_time = ARGV[4]

-- Validate inputs
if not ip_address then
    return redis.error_reply("IP address is required")
end
if not rate_limit then
    return redis.error_reply("Rate limit is required")
end

-- Determine the key
local key = user_id and user_id ~= "-1" and "user_data:" .. user_id or "ip:" .. ip_address
local user_exists = redis.call("EXISTS", key)

if user_exists == 1 then
    -- Get current values with proper defaults
    local requests_today = tonumber(redis.call("HGET", key, "requests_today")) or 0
    local remaining = tonumber(redis.call("HGET", key, "remaining_requests")) or rate_limit

    -- Ensure we don't go below zero remaining requests
    local new_remaining = math.max(0, remaining - 1)

    -- Update hash fields
    local updates = {
        "requests_today", requests_today + 1,
        "remaining_requests", new_remaining,
        "last_request", current_time
    }

    -- Preserve existing fields
    local user_type = redis.call("HGET", key, "tier")
    if not user_type then
        table.insert(updates, "tier")
        table.insert(updates, "unauthenticated")
    end

    -- Ensure IP address is always set
    table.insert(updates, "ip_address")
    table.insert(updates, ip_address)

    redis.call("HMSET", key, unpack(updates))
    redis.call("EXPIRE", key, 86400)

    -- Return all fields
    return redis.call("HGETALL", key)
else
    -- Create new user hash with complete field set
    local fields = {
        "id", user_id ~= "-1" and user_id or "",
        "username", "ip:" .. ip_address,
        "ip_address", ip_address,
        "tier", "unauthenticated",
        "remaining_requests", tostring(rate_limit - 1),
        "requests_today", "1",
        "last_request", current_time
    }

    redis.call("HMSET", key, unpack(fields))
    redis.call("EXPIRE", key, 86400)

    -- Return all fields
    return redis.call("HGETALL", key)
end
"""

# Script for rate limiting with hash-based counters
RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local current_time = tonumber(redis.call('TIME')[1])

if not window or not limit then
    return redis.error_reply("Window and limit are required")
end

-- Clean up old entries
local cleanup_before = current_time - window
local keys_to_del = {}
local cursor = "0"
repeat
    local scan_result = redis.call("HSCAN", key, cursor)
    cursor = scan_result[1]
    local pairs = scan_result[2]

    for i = 1, #pairs, 2 do
        local timestamp = tonumber(pairs[i])
        if timestamp and timestamp < cleanup_before then
            table.insert(keys_to_del, pairs[i])
        end
    end
until cursor == "0"

-- Delete old entries if any found
if #keys_to_del > 0 then
    redis.call("HDEL", key, unpack(keys_to_del))
end

-- Get current window count
local window_count = 0
local current_field = tostring(current_time)
window_count = redis.call("HINCRBY", key, current_field, 1)

-- Set expiration on first hit
if window_count == 1 then
    redis.call("EXPIRE", key, window)
end

-- Check if over limit
if window_count > limit then
    return -1
end

return window_count
"""

# Script to retrieve all user and client data stored in Redis
GET_ALL_USER_DATA_SCRIPT = """
local user_keys = redis.call('KEYS', 'user_data:*')
local ip_keys = redis.call('KEYS', 'ip:*')
local all_data = {}

local function process_user_data(key, type)
    local data = redis.call('HGETALL', key)
    if #data > 0 then
        local identifier = string.sub(key, type == 'user' and string.len('user_data:') + 1 or string.len('ip:') + 1)
        local formatted_data = {type, identifier}

        -- Create a table for the fields
        local fields = {}
        for i = 1, #data, 2 do
            -- Convert numeric strings to numbers where appropriate
            local value = data[i + 1]
            local field = data[i]
            if field == "requests_today" or field == "remaining_requests" then
                value = tonumber(value) or value
            end
            table.insert(formatted_data, {field, value})
        end

        -- Add required fields if missing
        local has_fields = {}
        for i = 1, #data, 2 do
            has_fields[data[i]] = true
        end

        -- Check and add missing required fields
        local required_fields = {
            "requests_today", "0",
            "remaining_requests", "0",
            "tier", "unauthenticated",
            "last_request", ""
        }

        for i = 1, #required_fields, 2 do
            local field = required_fields[i]
            if not has_fields[field] then
                table.insert(formatted_data, {field, required_fields[i + 1]})
            end
        end

        table.insert(all_data, formatted_data)
    end
end

-- Process user data
for _, key in ipairs(user_keys) do
    process_user_data(key, 'user')
end

-- Process IP data
for _, key in ipairs(ip_keys) do
    process_user_data(key, 'ip')
end

return all_data
"""
