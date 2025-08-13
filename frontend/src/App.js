import React, { useState, useEffect, useRef } from 'react';
import './App.css';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [sessionId, setSessionId] = useState('');
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Load session ID from localStorage on component mount
  useEffect(() => {
    const savedSessionId = localStorage.getItem('bakery_chat_session_id');
    if (savedSessionId) {
      setSessionId(savedSessionId);
    } else {
      createNewSession();
    }
  }, []);

  // Scroll to bottom of messages when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const createNewSession = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({})
      });
      
      const data = await response.json();
      setSessionId(data.session_id);
      localStorage.setItem('bakery_chat_session_id', data.session_id);
      
      // Add welcome message
      setMessages([{
        id: Date.now(),
        role: 'assistant',
        text: 'Hello! Welcome to Sunrise Bakery. I can help you with information about our hours, locations, menu items, and services. How can I assist you today?'
      }]);
    } catch (error) {
      console.error('Error creating session:', error);
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    // Add user message to UI
    const userMessage = {
      id: Date.now(),
      role: 'user',
      text: inputMessage
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      // Send message to backend
      const response = await fetch(`${API_BASE_URL}/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          query: inputMessage
        })
      });

      const data = await response.json();
      
      // Add assistant message to UI
      const assistantMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        text: data.response,
        citations: data.citations
      };
      
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        text: 'Sorry, I encountered an error processing your request. Please try again.'
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => {
    setMessages([]);
    createNewSession();
  };

  return (
    <div className="app">
      <div className="chat-container">
        <div className="chat-header">
          <h1>Sunrise Bakery Chatbot</h1>
          <button onClick={clearChat} className="clear-btn">New Chat</button>
        </div>
        
        <div className="messages-container">
          {messages.map((message) => (
            <div key={message.id} className={`message ${message.role}`}>
              <div className="message-content">
                <div className="message-text">{message.text}</div>
                {message.citations && message.citations.length > 0 && (
                  <div className="citations">
                    <strong>Sources:</strong>
                    <ul>
                      {message.citations.map((citation, index) => (
                        <li key={index} className="citation-item">
                          <span className="citation-source">{citation.source}</span>
                          <span className="citation-text">{citation.text}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="message assistant">
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        
        <div className="input-container">
          <textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask about our hours, menu, locations, or services..."
            disabled={isLoading}
            rows="3"
          />
          <button 
            onClick={sendMessage} 
            disabled={isLoading || !inputMessage.trim()}
            className="send-btn"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;