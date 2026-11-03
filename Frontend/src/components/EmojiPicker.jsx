import React, { useState, useEffect, useRef } from 'react'

const EMOJI_CATEGORIES = [
  {
    name: 'Smileys',
    icon: '😀',
    emojis: [
      '😀', '😃', '😄', '😁', '😆', '😅', '😂', '🤣', '😊', '😇',
      '🙂', '🙃', '😉', '😌', '😍', '🥰', '😘', '😗', '😙', '😚',
      '😋', '😛', '😜', '🤪', '😝', '🤑', '🤗', '🤭', '🤫', '🤔',
      '🤐', '🤨', '😐', '😑', '😶', '😏', '😒', '🙄', '😬', '🤥',
      '😔', '😪', '🤤', '😴', '😷', '🤒', '🤕', '🤢', '🤮', '🥵',
      '🥶', '🥴', '😵', '🤯', '🤠', '🥳', '😎', '🤓', '🧐', '😕',
    ],
  },
  {
    name: 'Gestures',
    icon: '👍',
    emojis: [
      '👍', '👎', '👌', '✌️', '🤞', '🤟', '🤘', '🤙', '👈', '👉',
      '👆', '🖕', '👇', '☝️', '✋', '🤚', '🖐️', '🖖', '👋', '🤙',
      '💪', '🦾', '👏', '🙌', '👐', '🤲', '🤝', '🙏', '✍️', '💅',
    ],
  },
  {
    name: 'Hearts & Vibes',
    icon: '❤️',
    emojis: [
      '❤️', '🧡', '💛', '💚', '💙', '💜', '🖤', '🤍', '🤎', '💔',
      '❣️', '💕', '💞', '💓', '💗', '💖', '💘', '💝', '💟', '🔥',
      '✨', '🌟', '⭐', '💫', '💥', '💯', '🎉', '🎊', '🎈', '🚀',
    ],
  },
  {
    name: 'Reactions',
    icon: '🔥',
    emojis: [
      '🔥', '💯', '👏', '🎉', '✨', '⚡', '💡', '🏆', '🥇', '👑',
      '👀', '🎯', '🌈', '☀️', '☕', '🍻', '🍕', '🍔', '🍦', '🍰',
    ],
  },
]

export default function EmojiPicker({ onSelectEmoji, onClose }) {
  const [activeCategory, setActiveCategory] = useState(0)
  const pickerRef = useRef(null)

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('touchstart', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('touchstart', handleClickOutside)
    }
  }, [onClose])

  return (
    <div className="emoji-picker-container" ref={pickerRef}>
      {/* Category Tabs */}
      <div className="emoji-category-bar">
        {EMOJI_CATEGORIES.map((cat, idx) => (
          <button
            key={cat.name}
            type="button"
            className={`emoji-cat-btn ${activeCategory === idx ? 'active' : ''}`}
            onClick={() => setActiveCategory(idx)}
            title={cat.name}
          >
            {cat.icon}
          </button>
        ))}
        <button
          type="button"
          className="emoji-cat-btn emoji-close-btn"
          onClick={onClose}
          title="Close"
        >
          ✕
        </button>
      </div>

      {/* Emoji Grid */}
      <div className="emoji-grid-scroll">
        <div className="emoji-grid">
          {EMOJI_CATEGORIES[activeCategory].emojis.map((emoji, idx) => (
            <button
              key={`${emoji}-${idx}`}
              type="button"
              className="emoji-item-btn"
              onClick={() => onSelectEmoji(emoji)}
            >
              {emoji}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

