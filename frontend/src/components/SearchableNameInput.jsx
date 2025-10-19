"use client"

import * as React from "react"
import { Check, Search } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import { cn } from "@/lib/utils"

export function SearchableNameInput({
  value = "",
  onChange,
  onSelectName,
  placeholder = "Enter name...",
  names = [],
  onKeyPress,
  className,
  autoFocus = false
}) {
  const [open, setOpen] = React.useState(false)
  const [inputValue, setInputValue] = React.useState(value)
  const inputRef = React.useRef(null)

  const formatSelectionValue = React.useCallback((entry) => {
    if (!entry) return ''
    const base = entry.display_name || ''
    const studentId = entry.student_id ? String(entry.student_id).trim() : ''
    if (studentId && base && !base.toLowerCase().includes(studentId.toLowerCase())) {
      return `${base} (${studentId})`
    }
    if (studentId && !base) {
      return studentId
    }
    return base
  }, [])

  // Filter names based on input value
  const filteredNames = React.useMemo(() => {
    if (!inputValue.trim()) return names
    const searchTerm = inputValue.toLowerCase()
    return names.filter(name => {
      const displayName = name.display_name?.toLowerCase() || ""
      const studentId = String(name.student_id || "").toLowerCase()
      return displayName.includes(searchTerm) || (studentId && studentId.includes(searchTerm))
    })
  }, [names, inputValue])

  const handleInputChange = (e) => {
    const newValue = e.target.value
    setInputValue(newValue)
    onChange?.(newValue, { source: 'input' })
    
    // Show dropdown when typing and there are matches
    if (newValue && filteredNames.length > 0) {
      setOpen(true)
    } else {
      setOpen(false)
    }
  }

  const handleSelectName = (selectedName) => {
    const displayValue = formatSelectionValue(selectedName)
    setInputValue(displayValue)
    onChange?.(displayValue, { source: 'selection', name: selectedName })
    onSelectName?.(selectedName)
    setOpen(false)
    // Keep focus on input after selection
    setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus()
      }
    }, 0)
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !open) {
      onKeyPress?.(e)
    }
    if (e.key === 'ArrowDown' && filteredNames.length > 0) {
      e.preventDefault()
      setOpen(true)
    }
    if (e.key === 'Escape') {
      setOpen(false)
      if (inputRef.current) {
        inputRef.current.focus()
      }
    }
  }

  const handleInputFocus = () => {
    if (inputValue && filteredNames.length > 0) {
      setOpen(true)
    }
  }

  const handleInputBlur = (e) => {
    // Don't close dropdown if clicking on a dropdown item
    setTimeout(() => {
      if (!e.currentTarget.contains(document.activeElement)) {
        setOpen(false)
      }
    }, 150)
  }

  React.useEffect(() => {
    setInputValue(value)
  }, [value])

  return (
    <div className="relative">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <div className="relative">
            <Input
              ref={inputRef}
              type="text"
              placeholder={placeholder}
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyPress}
              onFocus={handleInputFocus}
              onBlur={handleInputBlur}
              className={cn("pr-8", className)}
              autoFocus={autoFocus}
            />
            {filteredNames.length > 0 && inputValue && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="absolute right-0 top-0 h-full px-2 py-0 hover:bg-transparent"
                onMouseDown={(e) => {
                  e.preventDefault() // Prevent input from losing focus
                  setOpen(!open)
                }}
              >
                <Search className="h-4 w-4 text-muted-foreground" />
              </Button>
            )}
          </div>
        </PopoverTrigger>
        
        {filteredNames.length > 0 && inputValue && (
          <PopoverContent 
            className="w-[--radix-popover-trigger-width] p-0" 
            align="start"
            side="bottom"
            onOpenAutoFocus={(e) => e.preventDefault()}
          >
            <Command>
              <CommandList>
                {filteredNames.length === 0 ? (
                  <CommandEmpty>No names found.</CommandEmpty>
                ) : (
                  <CommandGroup>
                    {filteredNames.slice(0, 10).map((name, index) => {
                      const optionKey = name.key || (name.student_id ? `id:${name.student_id}` : `${name.display_name || 'option'}-${index}`)
                      const optionValue = `${name.display_name || ''} ${name.student_id || ''}`.trim()
                      return (
                        <CommandItem
                          key={`${optionKey}-${index}`}
                          value={optionValue}
                          onSelect={() => handleSelectName(name)}
                          onMouseDown={(e) => e.preventDefault()}
                          className="flex items-center justify-between cursor-pointer"
                        >
                          <div className="flex flex-col">
                            <span className="font-medium">{name.display_name}</span>
                            {name.student_id && (
                              <span className="text-xs text-muted-foreground">ID: {name.student_id}</span>
                            )}
                          </div>
                          <Check className="ml-2 h-4 w-4 opacity-0 group-data-[selected=true]:opacity-100" />
                        </CommandItem>
                      )
                    })}
                    {filteredNames.length > 10 && (
                      <div className="px-2 py-1 text-xs text-muted-foreground text-center">
                        {filteredNames.length - 10} more results...
                      </div>
                    )}
                  </CommandGroup>
                )}
              </CommandList>
            </Command>
          </PopoverContent>
        )}
      </Popover>
    </div>
  )
}