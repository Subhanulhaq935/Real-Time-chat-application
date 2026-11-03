import React from 'react'

const REACTION_EMOJIS = ['👍', '❤️', '😂', '😮', '😢', '🙏']

export default function MessageReactionBar({ currentReaction, onReact, onClose }) {
  return (
    <div className="reaction-bar-popup" onClick={(e) => e.stopPropagation()}>
      {REACTION_EMOJIS.map((emoji) => {
        const isSelected = currentReaction === emoji
        return (
          <button
            key={emoji}
            type="button"
            className={`reaction-emoji-btn ${isSelected ? 'active-reacted' : ''}`}
            onClick={() => {
              onReact(isSelected ? 'remove' : emoji)
              if (onClose) onClose()
            }}
            title={isSelected ? 'Click to remove reaction' : emoji}
          >
            {emoji}
          </button>
        )
      })}

      {currentReaction && (
        <button
          type="button"
          className="reaction-remove-btn"
          onClick={() => {
            onReact('remove')
            if (onClose) onClose()
          }}
          title="Remove reaction"
        >
          ✕
        </button>
      )}
    </div>
  )
}
