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
  onSelect,
  placeholder = "Enter name...",
  names = [],
  onKeyPress,
  className,
  autoFocus = false
}) {
  const [open, setOpen] = React.useState(false)
  const [inputValue, setInputValue] = React.useState(value)
  const inputRef = React.useRef(null)

  // Filter names based on input value
  const filteredNames = React.useMemo(() => {
    if (!inputValue.trim()) return names
    const searchTerm = inputValue.toLowerCase()
    return names.filter(name => 
      name.display_name.toLowerCase().includes(searchTerm)
    )
  }, [names, inputValue])

  const handleInputChange = (e) => {
    const newValue = e.target.value
    setInputValue(newValue)
    onChange?.(newValue)
    
    // Show dropdown when typing and there are matches
    if (newValue && filteredNames.length > 0) {
      setOpen(true)
    } else {
      setOpen(false)
    }
  }

  const handleSelectName = (selectedName) => {
    setInputValue(selectedName.display_name)
    onChange?.(selectedName.display_name)
    onSelect?.(selectedName)
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
                    {filteredNames.slice(0, 10).map((name, index) => (
                      <CommandItem
                        key={`${name.student_id}-${index}`}
                        value={name.display_name}
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
                    ))}
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