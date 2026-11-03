import React, { useState, useRef, useEffect } from 'react'

function dataURItoBlob(dataURI) {
  try {
    if (!dataURI || !dataURI.includes(',')) return null
    const parts = dataURI.split(',')
    const mimeMatch = parts[0].match(/:(.*?);/)
    const mime = mimeMatch ? mimeMatch[1] : 'audio/webm'
    const byteString = atob(parts[1])
    const ab = new ArrayBuffer(byteString.length)
    const ia = new Uint8Array(ab)
    for (let i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i)
    }
    return new Blob([ab], { type: mime })
  } catch (err) {
    console.warn('dataURItoBlob conversion error:', err)
    return null
  }
}

export default function AudioMessagePlayer({ mediaUrl, duration, isMine }) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [totalDuration, setTotalDuration] = useState(duration || 0)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [blobSrc, setBlobSrc] = useState('')
  const [playError, setPlayError] = useState(false)

  const audioRef = useRef(null)

  // Convert base64 Data URI to Blob URL so browsers (Chrome, Safari, Firefox) can buffer and seek reliably
  useEffect(() => {
    if (!mediaUrl) return

    let objectUrl = ''
    if (mediaUrl.startsWith('data:')) {
      const blob = dataURItoBlob(mediaUrl)
      if (blob) {
        objectUrl = URL.createObjectURL(blob)
        setBlobSrc(objectUrl)
      } else {
        setBlobSrc(mediaUrl)
      }
    } else {
      setBlobSrc(mediaUrl)
    }

    return () => {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl)
      }
    }
  }, [mediaUrl])

  useEffect(() => {
    if (duration && duration > 0) {
      setTotalDuration(duration)
    }
  }, [duration])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const handleLoadedMetadata = () => {
      if (audio.duration && isFinite(audio.duration) && !isNaN(audio.duration) && audio.duration > 0) {
        setTotalDuration(Math.round(audio.duration))
      }
    }

    const handleDurationChange = () => {
      if (audio.duration && isFinite(audio.duration) && !isNaN(audio.duration) && audio.duration > 0) {
        setTotalDuration(Math.round(audio.duration))
      }
    }

    const handleTimeUpdate = () => {
      setCurrentTime(audio.currentTime)
      if ((!totalDuration || !isFinite(totalDuration)) && audio.duration && isFinite(audio.duration)) {
        setTotalDuration(Math.round(audio.duration))
      }
    }

    const handleEnded = () => {
      setIsPlaying(false)
      setCurrentTime(0)
    }

    const handleError = (e) => {
      console.warn('Audio element error:', e)
      setIsPlaying(false)
      setPlayError(true)
    }

    audio.addEventListener('loadedmetadata', handleLoadedMetadata)
    audio.addEventListener('durationchange', handleDurationChange)
    audio.addEventListener('timeupdate', handleTimeUpdate)
    audio.addEventListener('ended', handleEnded)
    audio.addEventListener('error', handleError)

    return () => {
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata)
      audio.removeEventListener('durationchange', handleDurationChange)
      audio.removeEventListener('timeupdate', handleTimeUpdate)
      audio.removeEventListener('ended', handleEnded)
      audio.removeEventListener('error', handleError)
    }
  }, [blobSrc, totalDuration])

  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio) return

    if (isPlaying) {
      audio.pause()
      setIsPlaying(false)
    } else {
      setPlayError(false)
      audio.playbackRate = playbackRate

      // If at end or near end, restart from beginning
      if (audio.ended || (totalDuration > 0 && audio.currentTime >= totalDuration - 0.2)) {
        audio.currentTime = 0
        setCurrentTime(0)
      }

      const playPromise = audio.play()
      if (playPromise !== undefined) {
        playPromise
          .then(() => {
            setIsPlaying(true)
          })
          .catch((err) => {
            console.error('Audio playback failed:', err)
            setIsPlaying(false)
            setPlayError(true)
          })
      }
    }
  }

  const handleSeek = (e) => {
    const audio = audioRef.current
    if (!audio) return
    const dur = totalDuration > 0 ? totalDuration : (isFinite(audio.duration) ? audio.duration : 0)
    if (!dur) return

    const rect = e.currentTarget.getBoundingClientRect()
    const clickX = e.clientX - rect.left
    const newFraction = Math.max(0, Math.min(1, clickX / rect.width))
    const newTime = newFraction * dur

    audio.currentTime = newTime
    setCurrentTime(newTime)
  }

  const toggleRate = () => {
    const rates = [1, 1.5, 2]
    const nextRate = rates[(rates.indexOf(playbackRate) + 1) % rates.length]
    setPlaybackRate(nextRate)
    if (audioRef.current) {
      audioRef.current.playbackRate = nextRate
    }
  }

  const formatTime = (secs) => {
    const total = Math.max(0, Math.floor(secs || 0))
    const m = Math.floor(total / 60)
    const s = total % 60
    return `${m}:${s < 10 ? '0' : ''}${s}`
  }

  const effectiveDuration = totalDuration > 0 ? totalDuration : 1
  const progressPercent = Math.min(100, Math.max(0, (currentTime / effectiveDuration) * 100))

  return (
    <div className={`audio-player-container ${isMine ? 'mine' : 'theirs'}`}>
      <audio
        ref={audioRef}
        src={blobSrc || mediaUrl}
        preload="auto"
        playsInline
      />

      {/* Play/Pause Button */}
      <button
        type="button"
        className={`audio-play-btn ${isPlaying ? 'playing' : ''}`}
        onClick={togglePlay}
        aria-label={isPlaying ? 'Pause' : 'Play voice message'}
      >
        {isPlaying ? (
          <span className="audio-icon-pause">⏸</span>
        ) : (
          <span className="audio-icon-play">▶</span>
        )}
      </button>

      {/* Progress & Waveform Track */}
      <div className="audio-track-wrapper" onClick={handleSeek} title="Click to seek">
        <div className="audio-waveform-bars">
          {[40, 75, 55, 90, 60, 100, 45, 80, 65, 95, 50, 70, 85, 60, 75, 90, 40, 80, 55, 70].map((h, i) => {
            const barFraction = (i / 20) * 100
            const isFilled = barFraction <= progressPercent
            return (
              <span
                key={i}
                className={`audio-bar ${isFilled ? 'filled' : ''} ${isPlaying && isFilled ? 'pulsing' : ''}`}
                style={{ height: `${h}%` }}
              />
            )
          })}
        </div>

        <div className="audio-time-row">
          <span className="audio-current-time">
            {formatTime(isPlaying ? currentTime : totalDuration)}
          </span>
          {playError ? (
            <span className="audio-error-hint" onClick={togglePlay} style={{ color: '#ef4444', cursor: 'pointer' }}>
              Tap to retry
            </span>
          ) : (
            <span className="audio-mic-badge">🎙️ Voice</span>
          )}
        </div>
      </div>

      {/* Playback speed multiplier (1x / 1.5x / 2x) */}
      <button
        type="button"
        className="audio-speed-btn"
        onClick={toggleRate}
        title="Toggle playback speed"
      >
        {playbackRate}x
      </button>
    </div>
  )
}
