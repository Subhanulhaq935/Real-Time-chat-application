import React from 'react'

const REACTION_EMOJIS = ['👍', '❤️', '😂', '😮', '😢', '🙏']

export default function MessageReactionBar({ onReact, onClose }) {
  return (
    <div className="reaction-bar-popup" onClick={(e) => e.stopPropagation()}>
      {REACTION_EMOJIS.map((emoji) => (
        <button
          key={emoji}
          type="button"
          className="reaction-emoji-btn"
          onClick={() => {
            onReact(emoji)
            if (onClose) onClose()
          }}
          title={emoji}
        >
          {emoji}
        </button>
      ))}
    </div>
  )
}
