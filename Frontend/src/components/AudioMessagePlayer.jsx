import React, { useState, useRef, useEffect } from 'react'

export default function AudioMessagePlayer({ mediaUrl, duration, isMine }) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [totalDuration, setTotalDuration] = useState(duration || 0)
  const [playbackRate, setPlaybackRate] = useState(1)
  const audioRef = useRef(null)

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const handleLoadedMetadata = () => {
      if (audio.duration && !isNaN(audio.duration) && isFinite(audio.duration)) {
        setTotalDuration(Math.round(audio.duration))
      }
    }

    const handleTimeUpdate = () => {
      setCurrentTime(audio.currentTime)
    }

    const handleEnded = () => {
      setIsPlaying(false)
      setCurrentTime(0)
    }

    audio.addEventListener('loadedmetadata', handleLoadedMetadata)
    audio.addEventListener('timeupdate', handleTimeUpdate)
    audio.addEventListener('ended', handleEnded)

    return () => {
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata)
      audio.removeEventListener('timeupdate', handleTimeUpdate)
      audio.removeEventListener('ended', handleEnded)
    }
  }, [mediaUrl])

  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio) return

    if (isPlaying) {
      audio.pause()
      setIsPlaying(false)
    } else {
      audio.playbackRate = playbackRate
      audio.play().then(() => setIsPlaying(true)).catch((err) => console.error('Audio play error:', err))
    }
  }

  const handleSeek = (e) => {
    const audio = audioRef.current
    if (!audio || !totalDuration) return
    const rect = e.currentTarget.getBoundingClientRect()
    const clickX = e.clientX - rect.left
    const newFraction = Math.max(0, Math.min(1, clickX / rect.width))
    const newTime = newFraction * totalDuration
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

  const progressPercent = totalDuration > 0 ? (currentTime / totalDuration) * 100 : 0

  return (
    <div className={`audio-player-container ${isMine ? 'mine' : 'theirs'}`}>
      <audio ref={audioRef} src={mediaUrl} preload="metadata" />

      {/* Play/Pause Button */}
      <button
        type="button"
        className="audio-play-btn"
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
      <div className="audio-track-wrapper" onClick={handleSeek}>
        <div className="audio-waveform-bars">
          {[40, 75, 55, 90, 60, 100, 45, 80, 65, 95, 50, 70, 85, 60, 75, 90, 40, 80, 55, 70].map((h, i) => {
            const barFraction = (i / 20) * 100
            const isFilled = barFraction <= progressPercent
            return (
              <span
                key={i}
                className={`audio-bar ${isFilled ? 'filled' : ''}`}
                style={{ height: `${h}%` }}
              />
            )
          })}
        </div>
        <div className="audio-time-row">
          <span className="audio-current-time">
            {formatTime(isPlaying ? currentTime : totalDuration)}
          </span>
          <span className="audio-mic-badge">🎙️</span>
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
