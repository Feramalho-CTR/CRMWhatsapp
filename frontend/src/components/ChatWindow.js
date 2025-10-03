import React, { useState, useEffect, useRef } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from './ui/dropdown-menu';
import { api } from '../App';

const ChatWindow = ({ conversation, currentUser, onSendMessage, onStatusUpdate }) => {
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [sendingMessage, setSendingMessage] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    const fetchMessages = async () => {
      if (!conversation?.client?.id) return;
      
      setLoading(true);
      try {
        const response = await api.get(`/clients/${conversation.client.id}/messages`);
        setMessages(response.data);
      } catch (error) {
        console.error('Erro ao buscar mensagens:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchMessages();
  }, [conversation?.client?.id]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || sendingMessage) return;

    setSendingMessage(true);
    try {
      const messageData = {
        client_id: conversation.client.id,
        sender_type: 'agent',
        sender_id: currentUser.id,
        content: newMessage.trim()
      };

      await onSendMessage(messageData);
      
      // Add message locally for immediate feedback
      const tempMessage = {
        ...messageData,
        id: `temp-${Date.now()}`,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, tempMessage]);
      setNewMessage('');
      
      // Refresh messages to get the real one from server
      setTimeout(async () => {
        try {
          const response = await api.get(`/clients/${conversation.client.id}/messages`);
          setMessages(response.data);
        } catch (error) {
          console.error('Erro ao atualizar mensagens:', error);
        }
      }, 500);
      
    } catch (error) {
      console.error('Erro ao enviar mensagem:', error);
      // TODO: Show error toast
    } finally {
      setSendingMessage(false);
    }
  };

  const handleStatusChange = async (newStatus, assignedAgent = null) => {
    try {
      await onStatusUpdate(conversation.client.id, newStatus, assignedAgent);
    } catch (error) {
      console.error('Erro ao alterar status:', error);
      // TODO: Show error toast
    }
  };

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString('pt-BR', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getMessageBubbleStyle = (senderType) => {
    switch (senderType) {
      case 'client':
        return 'bg-white border border-gray-200 text-gray-900 rounded-tr-2xl rounded-tl-2xl rounded-br-2xl';
      case 'agent':
        return 'bg-green-500 text-white rounded-tl-2xl rounded-tr-2xl rounded-bl-2xl ml-auto';
      case 'bot':
        return 'bg-blue-100 text-blue-900 border border-blue-200 rounded-tr-2xl rounded-tl-2xl rounded-br-2xl';
      default:
        return 'bg-gray-100 text-gray-900 rounded-lg';
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'bot':
        return 'bg-green-100 text-green-800';
      case 'human':
        return 'bg-blue-100 text-blue-800';
      case 'waiting':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'bot':
        return 'BOT';
      case 'human':
        return 'HUMANO';
      case 'waiting':
        return 'AGUARDANDO';
      default:
        return status.toUpperCase();
    }
  };

  if (!conversation) {
    return null;
  }

  return (
    <div className="flex flex-col h-full bg-white" data-testid="chat-window">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-gradient-to-br from-green-400 to-green-600 rounded-full flex items-center justify-center text-white font-medium">
            {conversation.client.name 
              ? conversation.client.name.charAt(0).toUpperCase()
              : conversation.client.phone_number.slice(-2)
            }
          </div>
          <div>
            <h3 className="font-semibold text-gray-900" data-testid="chat-client-name">
              {conversation.client.name || conversation.client.phone_number}
            </h3>
            <p className="text-sm text-gray-600">{conversation.client.phone_number}</p>
          </div>
          <Badge className={getStatusColor(conversation.client.status)}>
            {getStatusText(conversation.client.status)}
          </Badge>
        </div>

        <div className="flex items-center space-x-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" data-testid="status-change-button">
                Alterar Status
                <svg className="w-4 h-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                </svg>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem 
                onClick={() => handleStatusChange('bot')}
                data-testid="status-bot-option"
              >
                <div className="w-3 h-3 bg-green-500 rounded-full mr-2"></div>
                Atendimento por BOT
              </DropdownMenuItem>
              <DropdownMenuItem 
                onClick={() => handleStatusChange('human', currentUser.id)}
                data-testid="status-human-option"
              >
                <div className="w-3 h-3 bg-blue-500 rounded-full mr-2"></div>
                Assumir Atendimento
              </DropdownMenuItem>
              <DropdownMenuItem 
                onClick={() => handleStatusChange('waiting')}
                data-testid="status-waiting-option"
              >
                <div className="w-3 h-3 bg-red-500 rounded-full mr-2"></div>
                Aguardando Humano
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <Button variant="outline" size="sm" data-testid="chat-history-button">
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Histórico
          </Button>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50" data-testid="messages-container">
        {loading ? (
          <div className="flex justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-500"></div>
          </div>
        ) : messages.length === 0 ? (
          <div className="text-center py-8 text-gray-500" data-testid="no-messages">
            <div className="w-16 h-16 bg-gray-200 rounded-full mx-auto mb-4 flex items-center justify-center">
              <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <h3 className="font-medium mb-1">Nenhuma mensagem ainda</h3>
            <p className="text-sm">O histórico de mensagens aparecerá aqui</p>
          </div>
        ) : (
          messages.map((message, index) => (
            <div
              key={message.id}
              className={`flex ${message.sender_type === 'agent' ? 'justify-end' : 'justify-start'}`}
              data-testid={`message-${index}`}
            >
              <div className={`max-w-xs lg:max-w-md px-4 py-2 ${getMessageBubbleStyle(message.sender_type)}`}>
                <p className="text-sm leading-relaxed">{message.content}</p>
                <div className={`text-xs mt-1 ${message.sender_type === 'agent' ? 'text-green-100' : 'text-gray-500'}`}>
                  {formatTime(message.timestamp)}
                  {message.sender_type === 'bot' && (
                    <span className="ml-2 text-blue-600 font-medium">BOT</span>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Message Input */}
      <div className="p-4 border-t border-gray-200 bg-white">
        <form onSubmit={handleSendMessage} className="flex space-x-3">
          <Input
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Digite sua mensagem..."
            className="flex-1"
            disabled={sendingMessage}
            data-testid="message-input"
            onKeyPress={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage(e);
              }
            }}
          />
          <Button 
            type="submit" 
            disabled={sendingMessage || !newMessage.trim()}
            className="bg-green-500 hover:bg-green-600 text-white px-6"
            data-testid="send-message-button"
          >
            {sendingMessage ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
            ) : (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            )}
          </Button>
        </form>
        
        <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
          <span>Pressione Enter para enviar, Shift+Enter para nova linha</span>
          <span>
            {conversation.client.assigned_agent && (
              `Responsável: ${conversation.client.assigned_agent}`
            )}
          </span>
        </div>
      </div>
    </div>
  );
};

export default ChatWindow;