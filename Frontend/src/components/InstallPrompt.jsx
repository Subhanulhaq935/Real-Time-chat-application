import React, { useState, useEffect } from 'react'

export default function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState(null)
  const [canInstall, setCanInstall] = useState(false)
  const [isStandalone, setIsStandalone] = useState(false)
  const [showBanner, setShowBanner] = useState(false)
  const [showIOSModal, setShowIOSModal] = useState(false)
  const [isIOS, setIsIOS] = useState(false)

  useEffect(() => {
    // 1. Check if already installed / running in standalone mode
    const standalone =
      window.matchMedia('(display-mode: standalone)').matches ||
      window.navigator.standalone === true ||
      document.referrer.includes('android-app://')

    setIsStandalone(standalone)
    if (standalone) {
      return
    }

    // 2. Detect iOS / iPadOS
    const ios =
      /iPad|iPhone|iPod/.test(navigator.userAgent) &&
      !window.MSStream &&
      !standalone
    setIsIOS(ios)

    // Check if dismissed in this session
    const dismissed = sessionStorage.getItem('pwa_prompt_dismissed') === 'true'

    if (ios && !dismissed) {
      setShowBanner(true)
    }

    // 3. Listen for Chrome / Edge / Android beforeinstallprompt
    const handleBeforeInstall = (e) => {
      e.preventDefault()
      setDeferredPrompt(e)
      setCanInstall(true)
      if (!dismissed) {
        setShowBanner(true)
      }
    }

    // 4. Listen for appinstalled
    const handleAppInstalled = () => {
      setDeferredPrompt(null)
      setCanInstall(false)
      setShowBanner(false)
      setIsStandalone(true)
      console.log('ChatApp successfully installed!')
    }

    window.addEventListener('beforeinstallprompt', handleBeforeInstall)
    window.addEventListener('appinstalled', handleAppInstalled)

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstall)
      window.removeEventListener('appinstalled', handleAppInstalled)
    }
  }, [])

  const handleInstallClick = async () => {
    if (deferredPrompt) {
      deferredPrompt.prompt()
      const { outcome } = await deferredPrompt.userChoice
      if (outcome === 'accepted') {
        setShowBanner(false)
      }
      setDeferredPrompt(null)
      setCanInstall(false)
    } else if (isIOS) {
      setShowIOSModal(true)
    }
  }

  const handleDismiss = () => {
    setShowBanner(false)
    sessionStorage.setItem('pwa_prompt_dismissed', 'true')
  }

  // If already running inside installed standalone app, render nothing
  if (isStandalone) {
    return null
  }

  // Only render if installable or iOS
  if (!canInstall && !isIOS) {
    return null
  }

  return (
    <>
      {/* Floating Bottom Installation Banner */}
      {showBanner && (
        <div className="pwa-install-banner" role="alert">
          <div className="pwa-banner-left">
            <img
              src="/pwa-192x192.png"
              alt="ChatApp Icon"
              className="pwa-banner-icon"
            />
            <div className="pwa-banner-text">
              <strong className="pwa-banner-title">Install ChatApp</strong>
              <span className="pwa-banner-desc">
                Install as a native app on your phone, tablet, or laptop.
              </span>
            </div>
          </div>
          <div className="pwa-banner-actions">
            <button
              type="button"
              onClick={handleInstallClick}
              className="pwa-btn-install"
            >
              📲 Install
            </button>
            <button
              type="button"
              onClick={handleDismiss}
              className="pwa-btn-dismiss"
              aria-label="Dismiss install banner"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* iOS Safari Home Screen Modal Instructions */}
      {showIOSModal && (
        <div className="modal-backdrop" onClick={() => setShowIOSModal(false)}>
          <div
            className="modal-card pwa-ios-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <h3>📱 Install on iPhone / iPad</h3>
              <button
                type="button"
                className="modal-close"
                onClick={() => setShowIOSModal(false)}
              >
                ✕
              </button>
            </div>
            <div className="pwa-ios-body">
              <p className="pwa-ios-intro">
                Apple Safari does not allow automatic one-click installation, but you can easily add ChatApp to your Home Screen:
              </p>
              <ol className="pwa-ios-steps">
                <li>
                  Tap the <strong>Share</strong> button at the bottom of Safari <span className="pwa-share-glyph">⎋</span> (square with arrow pointing up).
                </li>
                <li>
                  Scroll down the share menu and tap <strong>Add to Home Screen</strong> <span className="pwa-plus-glyph">⊞</span>.
                </li>
                <li>
                  Tap <strong>Add</strong> in the top right corner.
                </li>
              </ol>
              <div className="pwa-ios-footer">
                <button
                  type="button"
                  className="button-primary"
                  onClick={() => setShowIOSModal(false)}
                >
                  Got It!
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
