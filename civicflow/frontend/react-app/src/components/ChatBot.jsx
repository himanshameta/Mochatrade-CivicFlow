import React, { useState, useEffect } from 'react'
import axios from 'axios'

const ChatBot = ({ user, showToast }) => {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [stage, setStage] = useState('welcome')

  useEffect(() => {
    if (isOpen && messages.length === 0) {
      setMessages([
        {
          role: 'assistant',
          content: 'Hello! I\'m Sahayak, your AI assistant. How can I help you today?'
        }
      ])
    }
  }, [isOpen])

  const sendMessage = async () => {
    if (!input.trim()) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setLoading(true)

    try {
      const response = await axios.post('/chat', {
        message: userMessage,
        session_id: '',
        stage: stage
      })

      const data = response.data.data
      
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.response
      }])

      if (data.triggered_action) {
        handleTriggeredAction(data.triggered_action)
      }

      if (data.fallback_mode) {
        showToast('AI counsellor is currently limited', 'warning')
      }
    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'I\'m having trouble right now. Please try again later.'
      }])
      showToast('Failed to send message', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleTriggeredAction = (action) => {
    if (action.action_type === 'navigate') {
      setTimeout(() => {
        window.location.href = action.target
      }, 1000)
    } else if (action.action_type === 'upload_document') {
      showToast('Please upload your document', 'info')
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <>
      <button
        className="chat-bot-toggle"
        onClick={() => setIsOpen(!isOpen)}
        title="Chat with Sahayak"
      >
        {isOpen ? '✕' : '💬'}
      </button>

      {isOpen && (
        <div className="chat-bot-window glass-card">
          <div className="chat-bot-header">
            <div className="chat-bot-avatar">🤖</div>
            <div>
              <h4>Sahayak AI</h4>
              <p>Your form filling assistant</p>
            </div>
          </div>

          <div className="chat-bot-messages">
            {messages.map((msg, i) => (
              <div key={i} className={`chat-message ${msg.role}`}>
                <div className="message-content">{msg.content}</div>
              </div>
            ))}
            {loading && (
              <div className="chat-message assistant">
                <div className="message-content typing-indicator">
                  <span></span><span></span><span></span>
                </div>
              </div>
            )}
          </div>

          <div className="chat-bot-input">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your message..."
              rows="2"
              disabled={loading}
            />
            <button
              className="btn btn-primary btn-sm"
              onClick={sendMessage}
              disabled={loading || !input.trim()}
            >
              Send
            </button>
          </div>
        </div>
      )}
    </>
  )
}

export default ChatBot
