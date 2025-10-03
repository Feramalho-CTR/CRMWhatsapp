import React from 'react';
import { Badge } from './ui/badge';

const ConversationList = ({ conversations, selectedConversation, onConversationSelect, loading }) => {
  const getStatusColor = (status) => {
    switch (status) {
      case 'bot':
        return 'bg-green-100 text-green-800';
      case 'human':
        return 'bg-blue-100 text-blue-800';
      case 'waiting':
        return 'bg-red-100 text-red-800';
      case 'finished':
        return 'bg-gray-100 text-gray-600';
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

  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    // Se for hoje, mostra apenas a hora
    if (diff < 86400000) {
      return date.toLocaleTimeString('pt-BR', { 
        hour: '2-digit', 
        minute: '2-digit' 
      });
    }
    
    // Se for ontem
    if (diff < 172800000) {
      return 'Ontem';
    }
    
    // Se for esta semana
    if (diff < 604800000) {
      return date.toLocaleDateString('pt-BR', { weekday: 'short' });
    }
    
    // Data completa
    return date.toLocaleDateString('pt-BR', { 
      day: '2-digit', 
      month: '2-digit' 
    });
  };

  if (loading) {
    return (
      <div className="flex-1 p-4">
        <div className="space-y-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="animate-pulse">
              <div className="flex items-center space-x-3 p-3">
                <div className="w-12 h-12 bg-gray-300 rounded-full"></div>
                <div className="flex-1">
                  <div className="h-4 bg-gray-300 rounded w-3/4 mb-2"></div>
                  <div className="h-3 bg-gray-300 rounded w-1/2"></div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" data-testid="conversation-list">
      <div className="p-4 border-b border-gray-200 bg-white">
        <h2 className="text-lg font-semibold text-gray-900">Conversas</h2>
        <p className="text-sm text-gray-600">{conversations.length} ativas</p>
      </div>
      
      <div className="flex-1 overflow-y-auto">
        {conversations.length === 0 ? (
          <div className="p-8 text-center text-gray-500" data-testid="no-conversations">
            <div className="w-16 h-16 bg-gray-200 rounded-full mx-auto mb-4 flex items-center justify-center">
              <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a2 2 0 01-2-2v-6a2 2 0 012-2h8V4l4 4z" />
              </svg>
            </div>
            <h3 className="font-medium mb-1">Nenhuma conversa</h3>
            <p className="text-sm">As conversas aparecerão aqui quando os clientes enviarem mensagens</p>
          </div>
        ) : (
          <div className="space-y-1">
            {conversations.map((conversation) => {
              const isSelected = selectedConversation?.client.id === conversation.client.id;
              const lastMessage = conversation.messages[0];
              
              return (
                <div
                  key={conversation.client.id}
                  className={`
                    cursor-pointer transition-all duration-200 border-l-4 hover:bg-gray-50
                    ${isSelected 
                      ? 'bg-green-50 border-l-green-500' 
                      : 'bg-white border-l-transparent hover:border-l-gray-300'
                    }
                  `}
                  onClick={() => onConversationSelect(conversation)}
                  data-testid={`conversation-item-${conversation.client.phone_number}`}
                >
                  <div className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 bg-gradient-to-br from-green-400 to-green-600 rounded-full flex items-center justify-center text-white font-medium">
                          {conversation.client.name 
                            ? conversation.client.name.charAt(0).toUpperCase()
                            : conversation.client.phone_number.slice(-2)
                          }
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="font-medium text-gray-900 truncate">
                            {conversation.client.name || conversation.client.phone_number}
                          </h3>
                          <p className="text-xs text-gray-500">
                            {conversation.client.phone_number}
                          </p>
                        </div>
                      </div>
                      <Badge className={getStatusColor(conversation.client.status)}>
                        {getStatusText(conversation.client.status)}
                      </Badge>
                    </div>
                    
                    {lastMessage && (
                      <div className="space-y-1">
                        <p className="text-sm text-gray-600 truncate">
                          {lastMessage.sender_type === 'client' ? '' : 'Você: '}
                          {lastMessage.content}
                        </p>
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-gray-400">
                            {formatTime(lastMessage.timestamp)}
                          </span>
                          {conversation.unread_count > 0 && (
                            <span className="bg-green-500 text-white text-xs rounded-full px-2 py-1 min-w-[20px] text-center">
                              {conversation.unread_count}
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default ConversationList;