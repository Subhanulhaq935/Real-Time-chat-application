import React, { useState, useEffect, useRef } from 'react'

export default function VoiceRecorderBar({ onSendAudio, onCancel }) {
  const [seconds, setSeconds] = useState(0)
  const [isRecording, setIsRecording] = useState(false)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const streamRef = useRef(null)
  const timerRef = useRef(null)
  const startTimeRef = useRef(Date.now())
  const isStoppedRef = useRef(false)

  useEffect(() => {
    let isMounted = true

    const startRecording = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        })

        if (!isMounted) {
          stream.getTracks().forEach((track) => track.stop())
          return
        }
        streamRef.current = stream

        // Detect best supported MIME type across Chrome, Safari, Firefox
        let mimeType = ''
        const candidates = [
          'audio/webm;codecs=opus',
          'audio/webm',
          'audio/mp4',
          'audio/aac',
          'audio/ogg;codecs=opus',
        ]
        if (typeof MediaRecorder !== 'undefined' && typeof MediaRecorder.isTypeSupported === 'function') {
          for (const cand of candidates) {
            if (MediaRecorder.isTypeSupported(cand)) {
              mimeType = cand
              break
            }
          }
        }

        const options = mimeType ? { mimeType } : {}
        const mediaRecorder = new MediaRecorder(stream, options)
        mediaRecorderRef.current = mediaRecorder
        audioChunksRef.current = []
        startTimeRef.current = Date.now()

        mediaRecorder.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) {
            audioChunksRef.current.push(e.data)
          }
        }

        // Slice every 250ms to accumulate audio data smoothly
        mediaRecorder.start(250)
        setIsRecording(true)

        timerRef.current = setInterval(() => {
          setSeconds((prev) => prev + 1)
        }, 1000)
      } catch (err) {
        console.error('Microphone access error:', err)
        alert('Microphone access is needed to record voice notes. Please allow microphone permission.')
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
    if (isStoppedRef.current) return
    isStoppedRef.current = true

    if (timerRef.current) clearInterval(timerRef.current)
    const recorder = mediaRecorderRef.current

    if (recorder && recorder.state !== 'inactive') {
      recorder.onstop = () => {
        const mime = recorder.mimeType || 'audio/webm'
        const audioBlob = new Blob(audioChunksRef.current, { type: mime })
        const elapsedSecs = Math.max(1, Math.round((Date.now() - startTimeRef.current) / 1000))

        // Stop microphone stream tracks immediately to release hardware
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((t) => t.stop())
        }

        if (audioBlob.size < 50) {
          alert('Recording was too short or empty. Please try again.')
          onCancel()
          return
        }

        const reader = new FileReader()
        reader.onloadend = () => {
          const base64Data = reader.result
          if (base64Data) {
            onSendAudio(base64Data, elapsedSecs)
          } else {
            onCancel()
          }
        }
        reader.readAsDataURL(audioBlob)
      }

      // Stopping the recorder will automatically trigger the final ondataavailable and onstop
      recorder.stop()
    } else {
      onCancel()
    }
  }

  const handleDiscard = () => {
    if (isStoppedRef.current) return
    isStoppedRef.current = true

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
        <span className="rec-recording-label">Recording voice note...</span>
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
