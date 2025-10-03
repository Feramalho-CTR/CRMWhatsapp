import React, { useState, useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import ConversationList from './ConversationList';
import ChatWindow from './ChatWindow';
import Header from './Header';
import AdminPanel from './AdminPanel';
import Settings from './Settings';
import { api } from '../App';

const Dashboard = ({ user, onLogout }) => {
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAdminPanel, setShowAdminPanel] = useState(false);

  const fetchConversations = async () => {
    try {
      const response = await api.get('/conversations');
      setConversations(response.data);
    } catch (error) {
      console.error('Erro ao buscar conversas:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConversations();
    
    // Poll for updates every 5 seconds
    const interval = setInterval(fetchConversations, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleConversationSelect = (conversation) => {
    setSelectedConversation(conversation);
  };

  const handleSendMessage = async (messageData) => {
    try {
      await api.post('/whatsapp/send', messageData);
      // Refresh conversations after sending
      await fetchConversations();
      
      // Refresh selected conversation if it matches
      if (selectedConversation && selectedConversation.client.id === messageData.client_id) {
        const messages = await api.get(`/clients/${messageData.client_id}/messages`);
        setSelectedConversation({
          ...selectedConversation,
          messages: messages.data
        });
      }
    } catch (error) {
      console.error('Erro ao enviar mensagem:', error);
      throw error;
    }
  };

  const handleClientStatusUpdate = async (clientId, status, assignedAgent = null) => {
    try {
      const updateData = { status };
      if (assignedAgent) updateData.assigned_agent = assignedAgent;
      
      await api.put(`/clients/${clientId}`, updateData);
      await fetchConversations();
      
      // Update selected conversation if it matches
      if (selectedConversation && selectedConversation.client.id === clientId) {
        setSelectedConversation({
          ...selectedConversation,
          client: {
            ...selectedConversation.client,
            status,
            assigned_agent: assignedAgent
          }
        });
      }
    } catch (error) {
      console.error('Erro ao atualizar status:', error);
      throw error;
    }
  };

  if (showAdminPanel) {
    return (
      <AdminPanel 
        user={user} 
        onBack={() => setShowAdminPanel(false)} 
      />
    );
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50" data-testid="dashboard-container">
      <Header user={user} onLogout={onLogout} onShowAdmin={() => setShowAdminPanel(true)} />
      
      <div className="flex-1 flex overflow-hidden">
        <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
          <ConversationList
            conversations={conversations}
            selectedConversation={selectedConversation}
            onConversationSelect={handleConversationSelect}
            loading={loading}
          />
        </div>
        
        <div className="flex-1 flex flex-col">
          {selectedConversation ? (
            <ChatWindow
              conversation={selectedConversation}
              currentUser={user}
              onSendMessage={handleSendMessage}
              onStatusUpdate={handleClientStatusUpdate}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center bg-gray-100" data-testid="no-conversation-selected">
              <div className="text-center text-gray-500">
                <div className="w-20 h-20 bg-gray-300 rounded-full mx-auto mb-4 flex items-center justify-center">
                  <svg className="w-10 h-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium mb-1">Selecione uma conversa</h3>
                <p className="text-sm">Escolha uma conversa da lista para começar a atender</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;