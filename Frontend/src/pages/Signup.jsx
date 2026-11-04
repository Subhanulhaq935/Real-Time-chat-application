import React, { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { signup, verifyOtp, resendOtp } from '../api/auth'

export default function Signup() {
  const navigate = useNavigate()
  const location = useLocation()

  // Steps: 'signup' -> 'verify' -> 'success'
  const [step, setStep] = useState('signup')

  // Form State
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  // OTP State (6-digit array)
  const [otp, setOtp] = useState(['', '', '', '', '', ''])
  const otpInputsRef = useRef([])

  // UI State
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState(null)
  const [successNotice, setSuccessNotice] = useState(null)
  const [cooldown, setCooldown] = useState(0)

  // Countdown timer for resend OTP cooldown
  useEffect(() => {
    let timer
    if (cooldown > 0) {
      timer = setInterval(() => {
        setCooldown((prev) => prev - 1)
      }, 1000)
    }
    return () => clearInterval(timer)
  }, [cooldown])

  // Clear errors when user types
  const clearError = () => {
    if (errorMessage) setErrorMessage(null)
  }

  // Handle Signup Submit
  const handleSignupSubmit = async (e) => {
    e.preventDefault()
    clearError()

    if (!fullName.trim() || !email.trim() || !password) {
      setErrorMessage('Please fill in all required fields.')
      return
    }

    if (password.length < 8) {
      setErrorMessage('Password must be at least 8 characters long.')
      return
    }

    if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
      setErrorMessage('Password must contain at least one letter and one number.')
      return
    }

    if (password !== confirmPassword) {
      setErrorMessage('Passwords do not match.')
      return
    }

    setLoading(true)
    try {
      const res = await signup({
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        password,
      })
      setSuccessNotice(res.message || 'Verification code sent.')
      if (res.dev_otp && res.dev_otp.length === 6) {
        setOtp(res.dev_otp.split(''))
      }
      setCooldown(60)
      setStep('verify')
    } catch (err) {
      const detail = err.response?.data?.detail
      let msg = 'Signup failed. Please try again.'
      if (typeof detail === 'string') {
        msg = detail
      } else if (Array.isArray(detail) && detail.length > 0) {
        msg = detail.map((d) => d.msg || d).join(', ')
      } else if (err.message) {
        msg = err.message
      }
      setErrorMessage(msg)
    } finally {
      setLoading(false)
    }
  }

  // Handle OTP Digit Input
  const handleOtpChange = (index, value) => {
    clearError()
    if (!/^\d*$/.test(value)) return // Allow only digits

    const newOtp = [...otp]
    newOtp[index] = value.slice(-1) // Take only the latest character
    setOtp(newOtp)

    // Automatically focus next input box
    if (value && index < 5) {
      otpInputsRef.current[index + 1]?.focus()
    }
  }

  const handleOtpKeyDown = (index, e) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      otpInputsRef.current[index - 1]?.focus()
    }
  }

  const handleOtpPaste = (e) => {
    e.preventDefault()
    const pasted = e.clipboardData.getData('text').trim()
    if (/^\d{6}$/.test(pasted)) {
      const digits = pasted.split('')
      setOtp(digits)
      otpInputsRef.current[5]?.focus()
    }
  }

  // Handle OTP Verification Submit
  const handleVerifySubmit = async (e) => {
    e.preventDefault()
    clearError()

    const fullCode = otp.join('')
    if (fullCode.length !== 6) {
      setErrorMessage('Please enter the full 6-digit verification code.')
      return
    }

    setLoading(true)
    try {
      const res = await verifyOtp({
        email: email.trim().toLowerCase(),
        otp: fullCode,
      })
      setSuccessNotice(res.message)
      setStep('success')
    } catch (err) {
      const detail = err.response?.data?.detail
      let msg = 'Verification failed. Please try again.'
      if (typeof detail === 'string') {
        msg = detail
      } else if (Array.isArray(detail) && detail.length > 0) {
        msg = detail.map((d) => d.msg || d).join(', ')
      } else if (err.message) {
        msg = err.message
      }
      setErrorMessage(msg)
    } finally {
      setLoading(false)
    }
  }

  // Handle Resend OTP
  const handleResend = async () => {
    if (cooldown > 0 || loading) return
    clearError()
    setLoading(true)

    try {
      const res = await resendOtp({
        email: email.trim().toLowerCase(),
      })
      setSuccessNotice(res.message || 'A fresh code has been sent.')
      setCooldown(res.cooldown_seconds || 60)
      if (res.dev_otp && res.dev_otp.length === 6) {
        setOtp(res.dev_otp.split(''))
      } else {
        setOtp(['', '', '', '', '', ''])
        otpInputsRef.current[0]?.focus()
      }
    } catch (err) {
      const detail = err.response?.data?.detail
      let msg = 'Failed to resend code. Please try again.'
      if (typeof detail === 'string') {
        msg = detail
      } else if (Array.isArray(detail) && detail.length > 0) {
        msg = detail.map((d) => d.msg || d).join(', ')
      } else if (err.message) {
        msg = err.message
      }
      setErrorMessage(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        {/* Header */}
        <div className="auth-header">
          <div className="logo-icon">💬</div>
          <h1>Real-Time Chat</h1>
          <p className="subtitle">
            {step === 'signup' && 'Create your account to get started'}
            {step === 'verify' && 'Verify your email address'}
            {step === 'success' && 'Account activated successfully'}
          </p>
        </div>

        {/* Global Notifications */}
        {errorMessage && (
          <div className="alert alert-error">
            <span>⚠️ {errorMessage}</span>
          </div>
        )}

        {successNotice && step !== 'success' && (
          <div className="alert alert-success">
            <span>✉️ {successNotice}</span>
          </div>
        )}

        {/* STEP 1: SIGNUP FORM */}
        {step === 'signup' && (
          <form onSubmit={handleSignupSubmit} className="auth-form" noValidate>
            <div className="form-group">
              <label htmlFor="fullName">Full Name</label>
              <input
                id="fullName"
                type="text"
                placeholder="e.g. Alice Wonderland"
                value={fullName}
                onChange={(e) => {
                  setFullName(e.target.value)
                  clearError()
                }}
                disabled={loading}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="email">Email Address</label>
              <input
                id="email"
                type="email"
                placeholder="alice@example.com"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                  clearError()
                }}
                disabled={loading}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="password">Password</label>
              <div className="password-input-wrapper">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="At least 8 chars, 1 letter, 1 number"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    clearError()
                  }}
                  disabled={loading}
                  required
                />
                <button
                  type="button"
                  className="password-toggle-btn"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  title={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? '👁️‍🗨️' : '👁️'}
                </button>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="confirmPassword">Confirm Password</label>
              <div className="password-input-wrapper">
                <input
                  id="confirmPassword"
                  type={showConfirmPassword ? 'text' : 'password'}
                  placeholder="Re-enter your password"
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value)
                    clearError()
                  }}
                  disabled={loading}
                  required
                />
                <button
                  type="button"
                  className="password-toggle-btn"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                  title={showConfirmPassword ? "Hide password" : "Show password"}
                >
                  {showConfirmPassword ? '👁️‍🗨️' : '👁️'}
                </button>
              </div>
            </div>

            <button type="submit" className="button button-primary" disabled={loading}>
              {loading ? 'Creating Account & Sending OTP...' : 'Sign Up'}
            </button>

            <div className="auth-footer">
              <span>Already have an account? </span>
              <button
                type="button"
                className="link-button"
                onClick={() => navigate('/login')}
              >
                Log In
              </button>
            </div>
          </form>
        )}

        {/* STEP 2: OTP VERIFICATION */}
        {step === 'verify' && (
          <form onSubmit={handleVerifySubmit} className="auth-form">
            <div className="verify-instructions">
              <p>
                We've sent a 6-digit confirmation code to:
                <br />
                <strong>{email}</strong>
              </p>
            </div>

            <label className="otp-label">Enter 6-Digit Code</label>
            <div className="otp-inputs-grid" onPaste={handleOtpPaste}>
              {otp.map((digit, idx) => (
                <input
                  key={idx}
                  ref={(el) => (otpInputsRef.current[idx] = el)}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleOtpChange(idx, e.target.value)}
                  onKeyDown={(e) => handleOtpKeyDown(idx, e)}
                  disabled={loading}
                  className="otp-digit-input"
                  autoFocus={idx === 0}
                />
              ))}
            </div>

            <button type="submit" className="button button-primary" disabled={loading || otp.join('').length !== 6}>
              {loading ? 'Verifying Code...' : 'Verify Email'}
            </button>

            <div className="resend-section">
              <button
                type="button"
                className="button-link"
                onClick={handleResend}
                disabled={cooldown > 0 || loading}
              >
                {cooldown > 0 ? `Resend code in ${cooldown}s` : "Didn't receive a code? Resend"}
              </button>
            </div>

            <div className="auth-footer">
              <button
                type="button"
                className="button-secondary-link"
                onClick={() => {
                  setStep('signup')
                  clearError()
                  setSuccessNotice(null)
                }}
              >
                ← Back / Edit Email
              </button>
            </div>
          </form>
        )}

        {/* STEP 3: SUCCESS CONFIRMATION */}
        {step === 'success' && (
          <div className="success-card">
            <div className="success-icon">🎉</div>
            <h2>Verification Complete!</h2>
            <p>
              Your email <strong>{email}</strong> is verified and your account is active.
            </p>

            <div className="success-info-box">
              <p>Ready for Phase 4: Login &amp; Session Authentication</p>
            </div>

            <button
              type="button"
              className="button button-primary"
              onClick={() => navigate('/login')}
            >
              Proceed to Login
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

