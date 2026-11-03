import React, { useState, useEffect, useRef } from 'react'

export default function VoiceRecorderBar({ onSendAudio, onCancel }) {
  const [seconds, setSeconds] = useState(0)
  const [isRecording, setIsRecording] = useState(false)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const streamRef = useRef(null)
  const timerRef = useRef(null)

  useEffect(() => {
    let isMounted = true

    const startRecording = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        if (!isMounted) {
          stream.getTracks().forEach((track) => track.stop())
          return
        }
        streamRef.current = stream

        let mimeType = 'audio/webm'
        if (typeof MediaRecorder.isTypeSupported === 'function') {
          if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
            mimeType = 'audio/webm;codecs=opus'
          } else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
            mimeType = 'audio/ogg;codecs=opus'
          } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
            mimeType = 'audio/mp4'
          }
        }

        const mediaRecorder = new MediaRecorder(stream, { mimeType })
        mediaRecorderRef.current = mediaRecorder
        audioChunksRef.current = []

        mediaRecorder.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) {
            audioChunksRef.current.push(e.data)
          }
        }

        mediaRecorder.start(250) // slice every 250ms
        setIsRecording(true)

        timerRef.current = setInterval(() => {
          setSeconds((prev) => prev + 1)
        }, 1000)
      } catch (err) {
        console.error('Microphone access denied or error:', err)
        alert('Could not access microphone. Please allow microphone permissions in your browser.')
        onCancel()
      }
    }

    startRecording()

    return () => {
      isMounted = false
      if (timerRef.current) clearInterval(timerRef.current)
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop())
      }
    }
  }, [onCancel])

  const handleStopAndSend = () => {
    if (timerRef.current) clearInterval(timerRef.current)
    const recorder = mediaRecorderRef.current

    if (recorder && recorder.state !== 'inactive') {
      recorder.onstop = () => {
        const mime = recorder.mimeType || 'audio/webm'
        const audioBlob = new Blob(audioChunksRef.current, { type: mime })
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((t) => t.stop())
        }

        const reader = new FileReader()
        reader.onloadend = () => {
          const base64Data = reader.result
          onSendAudio(base64Data, Math.max(1, seconds))
        }
        reader.readAsDataURL(audioBlob)
      }
      recorder.stop()
    } else {
      onCancel()
    }
  }

  const handleDiscard = () => {
    if (timerRef.current) clearInterval(timerRef.current)
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
    }
    onCancel()
  }

  const formatTimer = (s) => {
    const mins = Math.floor(s / 60)
    const secs = s % 60
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`
  }

  return (
    <div className="voice-recorder-bar">
      <div className="voice-rec-left">
        <span className="rec-pulse-dot" />
        <span className="rec-timer-text">{formatTimer(seconds)}</span>
        <span className="rec-recording-label">Recording audio...</span>
      </div>

      <div className="voice-rec-actions">
        <button
          type="button"
          className="rec-btn-cancel"
          onClick={handleDiscard}
          title="Cancel and discard voice note"
        >
          🗑️ Cancel
        </button>
        <button
          type="button"
          className="rec-btn-send"
          onClick={handleStopAndSend}
          title="Send voice note"
        >
          Send ➤
        </button>
      </div>
    </div>
  )
}
