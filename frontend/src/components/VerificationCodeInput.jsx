import React, { useRef, useEffect } from 'react'

/**
 * A 6-digit PIN-style verification code input.
 * - Each digit has its own box for better visual clarity
 * - Auto-advances to next box when a digit is entered
 * - Supports backspace to go to previous box
 * - Supports paste of a full 6-digit code
 */
function VerificationCodeInput({ value, onChange, disabled }) {
  const inputRefs = useRef([])
  const CODE_LENGTH = 6

  // Convert value string to array of digits
  const digits = (value || '').split('').slice(0, CODE_LENGTH)
  while (digits.length < CODE_LENGTH) {
    digits.push('')
  }

  // Focus first empty input when component mounts or value becomes empty
  useEffect(() => {
    if (!disabled && value === '') {
      inputRefs.current[0]?.focus()
    }
  }, [disabled, value])

  const handleChange = (index, e) => {
    const inputValue = e.target.value

    // Only allow single digit
    if (inputValue.length > 1) {
      // If pasting, try to extract all digits
      const pastedDigits = inputValue.replace(/\D/g, '').slice(0, CODE_LENGTH)
      if (pastedDigits.length > 0) {
        onChange(pastedDigits)
        // Focus on the appropriate input after paste
        const focusIndex = Math.min(pastedDigits.length, CODE_LENGTH - 1)
        inputRefs.current[focusIndex]?.focus()
      }
      return
    }

    // Only allow digits
    if (inputValue && !/^\d$/.test(inputValue)) {
      return
    }

    // Build new code value
    const newDigits = [...digits]
    newDigits[index] = inputValue
    const newCode = newDigits.join('')
    onChange(newCode)

    // Auto-advance to next input if we entered a digit
    if (inputValue && index < CODE_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus()
    }
  }

  const handleKeyDown = (index, e) => {
    if (e.key === 'Backspace') {
      if (!digits[index] && index > 0) {
        // If current box is empty, go to previous box and clear it
        const newDigits = [...digits]
        newDigits[index - 1] = ''
        onChange(newDigits.join(''))
        inputRefs.current[index - 1]?.focus()
        e.preventDefault()
      }
    } else if (e.key === 'ArrowLeft' && index > 0) {
      inputRefs.current[index - 1]?.focus()
      e.preventDefault()
    } else if (e.key === 'ArrowRight' && index < CODE_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus()
      e.preventDefault()
    }
  }

  const handlePaste = (e) => {
    e.preventDefault()
    const pastedData = e.clipboardData.getData('text')
    const pastedDigits = pastedData.replace(/\D/g, '').slice(0, CODE_LENGTH)
    if (pastedDigits.length > 0) {
      onChange(pastedDigits)
      // Focus on the last filled input or the next empty one
      const focusIndex = Math.min(pastedDigits.length, CODE_LENGTH - 1)
      inputRefs.current[focusIndex]?.focus()
    }
  }

  const handleFocus = (e) => {
    // Select the content when focused
    e.target.select()
  }

  return (
    <div className="flex gap-2 justify-center">
      {digits.map((digit, index) => (
        <input
          key={index}
          ref={(el) => (inputRefs.current[index] = el)}
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={CODE_LENGTH}
          value={digit}
          onChange={(e) => handleChange(index, e)}
          onKeyDown={(e) => handleKeyDown(index, e)}
          onPaste={handlePaste}
          onFocus={handleFocus}
          disabled={disabled}
          className={`
            w-10 h-12 text-center text-xl font-mono font-bold
            border-2 rounded-lg
            focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500
            transition-all duration-150
            ${disabled
              ? 'bg-gray-100 border-gray-300 text-gray-400 cursor-not-allowed'
              : 'bg-white border-gray-300 hover:border-amber-400 text-gray-900'
            }
            ${digit ? 'border-amber-400 bg-amber-50' : ''}
          `}
          aria-label={`Verification code digit ${index + 1}`}
        />
      ))}
    </div>
  )
}

export default VerificationCodeInput
