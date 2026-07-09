--[[ 
    Memory Scanner Helper Addon
    
    Uses LuaJIT FFI to expose memory addresses and unit data.
    
    Usage:
    - /msc help     - Show commands
    - /msc player   - Show player details + memory addresses
    - /msc export   - Export all data for memory scanner
]]

local MSC = {}
MSC.VERSION = "1.1.0"

-- Try to load LuaJIT FFI
local ffi_ok, ffi = pcall(require, "ffi")
local jit_ok, jit = pcall(require, "jit")

----------------------------------------------------
-- Utility Functions
----------------------------------------------------

local function Chat(msg)
    local text = tostring(msg)
    if Command and Command.Console and Command.Console.Display then
        Command.Console.Display("general", true, text, true)
    else
        print(text)
    end
end

----------------------------------------------------
-- LuaJIT FFI: Get pointer from Lua number/table
----------------------------------------------------

-- FFI type for reading raw memory
if ffi_ok then
    ffi.cdef[[
        typedef struct { float x, y, z; } vec3f;
        typedef struct { double x, y, z; } vec3d;
        typedef struct { int32_t health; int32_t healthMax; } healthpair;
    ]]
end

-- Get the raw pointer address of a Lua value (number) via FFI
local function NumberToAddress(num)
    if not ffi_ok then return nil end
    if type(num) ~= "number" then return nil end
    
    -- Use a union to reinterpret the double as a pointer
    local ptr = ffi.new("void*[1]")
    local dbl = ffi.new("double[1]")
    dbl[0] = num
    ffi.copy(ptr, dbl, 8)
    return tonumber(ffi.cast("intptr_t", ptr[0]))
end

-- Get memory address of a table by exploiting __index metamethod
local function TableToAddress(tbl)
    if not ffi_ok or type(tbl) ~= "table" then return nil end
    
    -- Get pointer via casting the table userdata
    -- In LuaJIT, tables don't have a direct address, but we can find 
    -- the internal representation
    local ptr = ffi.cast("void*", tbl)
    return tonumber(ffi.cast("intptr_t", ptr))
end

-- Read raw memory at an address
local function ReadMemory(address, size)
    if not ffi_ok then return nil end
    local ptr = ffi.cast("void*", address)
    local buf = ffi.new("uint8_t[?]", size)
    ffi.copy(buf, ptr, size)
    return ffi.string(buf, size)
end

-- Read a float from memory
local function ReadFloat(address)
    if not ffi_ok then return nil end
    local ptr = ffi.cast("float*", address)
    return ptr[0]
end

-- Read a double from memory
local function ReadDouble(address)
    if not ffi_ok then return nil end
    local ptr = ffi.cast("double*", address)
    return ptr[0]
end

-- Read a uint32 from memory
local function ReadUint32(address)
    if not ffi_ok then return nil end
    local ptr = ffi.cast("uint32_t*", address)
    return ptr[0]
end

-- Read a uint64 from memory  
local function ReadUint64(address)
    if not ffi_ok then return nil end
    local ptr = ffi.cast("uint64_t*", address)
    return ptr[0]
end

-- Read a C string from memory
local function ReadCString(address, max_len)
    if not ffi_ok then return nil end
    max_len = max_len or 256
    local ptr = ffi.cast("const char*", address)
    local len = ffi.C.strnlen(ptr, max_len)
    return ffi.string(ptr, len)
end

----------------------------------------------------
-- Find LuaJIT Lua state pointer
----------------------------------------------------

local function FindLuaState()
    if not ffi_ok then return nil end
    
    -- LuaJIT stores the global state
    -- We can find it by walking the thread local storage
    -- But a simpler approach: the main thread's lua_State is accessible
    
    -- Try to get it from the registry
    local registry = debug.getregistry()
    if registry then
        return TableToAddress(registry)
    end
    return nil
end

----------------------------------------------------
-- Unit Data Extraction
----------------------------------------------------

local function GetUnitDetail(unitId)
    if Inspect and Inspect.Unit and Inspect.Unit.Detail then
        local ok, detail = pcall(Inspect.Unit.Detail, unitId)
        if ok then return detail end
    end
    return nil
end

local function GetUnitList()
    if Inspect and Inspect.Unit and Inspect.Unit.List then
        local ok, units = pcall(Inspect.Unit.List)
        if ok then return units or {} end
    end
    return {}
end

----------------------------------------------------
-- Memory Scanning
----------------------------------------------------

local function ScanForValue(value, value_type, start_addr, size)
    if not ffi_ok then return {} end
    
    local results = {}
    local buf_size = 4096
    local ptr = ffi.cast("uint8_t*", start_addr)
    
    for offset = 0, size - buf_size, buf_size do
        local chunk = ffi.string(ptr + offset, buf_size)
        
        local search_bytes
        if value_type == "float" then
            local tmp = ffi.new("float[1]")
            tmp[0] = value
            search_bytes = ffi.string(tmp, 4)
        elseif value_type == "double" then
            local tmp = ffi.new("double[1]")
            tmp[0] = value
            search_bytes = ffi.string(tmp, 8)
        elseif value_type == "int32" then
            local tmp = ffi.new("int32_t[1]")
            tmp[0] = value
            search_bytes = ffi.string(tmp, 4)
        elseif value_type == "int64" then
            local tmp = ffi.new("int64_t[1]")
            tmp[0] = value
            search_bytes = ffi.string(tmp, 8)
        end
        
        if search_bytes then
            local pos = 1
            while true do
                local idx = chunk:find(search_bytes, pos, true)
                if not idx then break end
                table.insert(results, start_addr + offset + idx - 1)
                pos = idx + 1
            end
        end
    end
    
    return results
end

----------------------------------------------------
-- Export Functions
----------------------------------------------------

local function ExportPlayerData()
    local detail = GetUnitDetail("player")
    if not detail then
        Chat("ERROR: Could not get player detail")
        return
    end
    
    Chat("[PLAYER]")
    
    -- Core identification
    for _, k in ipairs({"name","id","calling","level","raceName","guild","alliance","role","availability"}) do
        if detail[k] ~= nil then
            Chat("FIELD:" .. k .. "=" .. tostring(detail[k]))
        end
    end
    
    -- Numeric values (important for memory scanning)
    for _, k in ipairs({"health","healthMax","mana","manaMax","energy","energyMax","charge","chargeMax","power","planar","planarMax","vitality","combo","absorb","radius","level"}) do
        if detail[k] ~= nil then
            local v = detail[k]
            local hex = ""
            if ffi_ok and type(v) == "number" then
                -- Show as int32, float, and double
                local tmp32 = ffi.new("int32_t[1]"); tmp32[0] = v
                local tmpf = ffi.new("float[1]"); tmpf[0] = v
                local tmpd = ffi.new("double[1]"); tmpd[0] = v
                hex = string.format("  (i32:%s f:%s d:%s)",
                    ffi.string(tmp32, 4):reverse():gsub(".", function(c) return string.format("%02x", c:byte()) end),
                    ffi.string(tmpf, 4):reverse():gsub(".", function(c) return string.format("%02x", c:byte()) end),
                    ffi.string(tmpd, 8):reverse():gsub(".", function(c) return string.format("%02x", c:byte()) end))
            end
            Chat("FIELD:" .. k .. "=" .. tostring(v) .. hex)
        end
    end
    
    -- Coordinates
    for _, k in ipairs({"coordX","coordY","coordZ"}) do
        if detail[k] ~= nil then
            local v = detail[k]
            local hex = ""
            if ffi_ok and type(v) == "number" then
                local tmpf = ffi.new("float[1]"); tmpf[0] = v
                local tmpd = ffi.new("double[1]"); tmpd[0] = v
                hex = string.format("  (f:%s d:%s)",
                    ffi.string(tmpf, 4):reverse():gsub(".", function(c) return string.format("%02x", c:byte()) end),
                    ffi.string(tmpd, 8):reverse():gsub(".", function(c) return string.format("%02x", c:byte()) end))
            end
            Chat("FIELD:" .. k .. "=" .. tostring(v) .. hex)
        end
    end
    
    -- Try to get memory addresses via FFI
    if ffi_ok then
        Chat("[MEMORY]")
        
        -- Get table address
        local table_addr = TableToAddress(detail)
        Chat("TABLE_ADDR=" .. tostring(table_addr))
        
        -- Try to find the detail table's hash part
        -- In LuaJIT, a table has: keys, values, hash part
        -- The actual data might be stored inline for small tables
    end
end

local function ExportUnitList()
    local units = GetUnitList()
    local count = 0
    for _ in pairs(units) do count = count + 1 end
    Chat("[UNITS] count=" .. count)
    for unitId, _ in pairs(units) do
        local detail = GetUnitDetail(unitId)
        if detail then
            Chat("UNIT:" .. unitId .. ":" .. (detail.name or "?") .. ":" .. (detail.calling or "?") .. ":lv" .. tostring(detail.level or "?"))
        end
    end
end

local function ShowPlayer()
    local detail = GetUnitDetail("player")
    if not detail then
        Chat("Could not get player details")
        return
    end
    Chat("[Player Details]")
    local fields = {"name","id","calling","level","raceName","guild","alliance","role","availability",
        "health","healthMax","mana","manaMax","energy","energyMax","charge","chargeMax",
        "power","planar","planarMax","vitality","combo","absorb","radius",
        "coordX","coordY","coordZ","locationName"}
    for _, f in ipairs(fields) do
        if detail[f] ~= nil then
            Chat("  " .. f .. " = " .. tostring(detail[f]))
        end
    end
    
    -- FFI info
    if ffi_ok then
        Chat("  [FFI Available]")
        Chat("  Table address: " .. tostring(TableToAddress(detail)))
    else
        Chat("  [FFI NOT available]")
    end
end

local function ShowUnits()
    local units = GetUnitList()
    local count = 0
    for _ in pairs(units) do count = count + 1 end
    Chat("Found " .. count .. " units:")
    for unitId, _ in pairs(units) do
        local detail = GetUnitDetail(unitId)
        if detail then
            local x = detail.coordX and string.format("%.0f", detail.coordX) or "?"
            local y = detail.coordY and string.format("%.0f", detail.coordY) or "?"
            Chat("  " .. unitId .. ": " .. (detail.name or "?") ..
                " (" .. (detail.calling or "?") .. " Lv." .. tostring(detail.level or "?") ..
                ") pos=" .. x .. "," .. y)
        end
    end
end

local function ShowAPI()
    Chat("[API Availability]")
    local checks = {
        {"Inspect.Unit.Detail", Inspect and Inspect.Unit and Inspect.Unit.Detail},
        {"Inspect.Unit.List", Inspect and Inspect.Unit and Inspect.Unit.List},
        {"Command.Slash.Register", Command and Command.Slash and Command.Slash.Register},
        {"Command.Console.Display", Command and Command.Console and Command.Console.Display},
        {"LuaJIT FFI", ffi_ok},
        {"JIT", jit_ok},
    }
    for _, c in ipairs(checks) do
        Chat("  " .. c[1] .. ": " .. (c[2] and "YES" or "NO"))
    end
    
    if jit_ok then
        Chat("  JIT version: " .. tostring(jit.version))
    end
end

----------------------------------------------------
-- Command Handler
----------------------------------------------------

local function HandleCommand(commandText)
    local args = tostring(commandText or "")
    local cmd = args:match("^%s*(%S+)") or "help"

    if cmd == "player" then
        ShowPlayer()
    elseif cmd == "units" then
        ShowUnits()
    elseif cmd == "api" then
        ShowAPI()
    elseif cmd == "export" then
        Chat("=== MEMORY SCANNER DATA START ===")
        ExportPlayerData()
        ExportUnitList()
        Chat("=== MEMORY SCANNER DATA END ===")
    else
        Chat("[Memory Scanner Helper] v" .. MSC.VERSION)
        Chat("  /msc player   - Show player details + addresses")
        Chat("  /msc units    - List all units")
        Chat("  /msc api      - Show API availability")
        Chat("  /msc export   - Export all data (hex encoded)")
    end
end

----------------------------------------------------
-- Global Functions
----------------------------------------------------

function MSC_Help()     HandleCommand("help")   end
function MSC_Player()   HandleCommand("player") end
function MSC_Units()    HandleCommand("units")  end
function MSC_Api()      HandleCommand("api")    end
function MSC_Export()   HandleCommand("export") end

----------------------------------------------------
-- Slash Command Handler
----------------------------------------------------

local function onSlashCommand(eventHandle, commandText)
    local text = commandText
    if text == nil then text = eventHandle end
    HandleCommand(text or "")
end

----------------------------------------------------
-- Initialization
----------------------------------------------------

local function OnLoad()
    Chat('<font color="#00FF00">[Memory Scanner Helper]</font> <font color="#FFFFFF">v' .. MSC.VERSION .. ' loaded. FFI=' .. (ffi_ok and "YES" or "NO") .. '. Type</font> <font color="#FFFF00">/msc help</font> <font color="#FFFFFF">for commands.</font>')

    if type(Command) ~= "table"
        or type(Command.Slash) ~= "table"
        or type(Command.Slash.Register) ~= "function"
        or type(Command.Event) ~= "table"
        or type(Command.Event.Attach) ~= "function" then
        return
    end

    local ok1, ev1 = pcall(Command.Slash.Register, "msc")
    if ok1 and ev1 then
        pcall(Command.Event.Attach, ev1, onSlashCommand, "MemoryScannerHelper msc")
    end

    local ok2, ev2 = pcall(Command.Slash.Register, "memscan")
    if ok2 and ev2 then
        pcall(Command.Event.Attach, ev2, onSlashCommand, "MemoryScannerHelper memscan")
    end
end

if Command and Command.Event and Command.Event.Register then
    Command.Event.Register("Addon.Startup.End", OnLoad)
else
    OnLoad()
end
