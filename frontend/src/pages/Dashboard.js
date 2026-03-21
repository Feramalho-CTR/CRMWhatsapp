import React, { useState, useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import ConversationList from '../components/ConversationList';
import ChatWindow from '../components/ChatWindow';
import Header from '../components/Header';
import AdminPanel from '../components/AdminPanel';
import Settings from '../components/Settings';
import Profile from '../components/Profile';
import { api } from '../App';
import { useAuth } from '../contexts/AuthContext';

const Dashboard = () => {
  const { user, logout } = useAuth();
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAdminPanel, setShowAdminPanel] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [currentUser, setCurrentUser] = useState(user);
  const [toast, setToast] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const wsConnectedRef = React.useRef(false);

  const showToast = (message, type = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  };

  const fetchConversations = async () => {
    try {
      const response = await api.get('/conversations');
      const data = response.data;
      // Trata se o backend retornar { value: [], Count: X } ou apenas []
      const conversationList = Array.isArray(data) ? data : (data.value || []);
      setConversations(conversationList);
    } catch (error) {
      console.error('Erro ao buscar conversas:', error);
    } finally {
      setLoading(false);
    }
  };

  const selectedConversationRef = React.useRef(selectedConversation);
  useEffect(() => { selectedConversationRef.current = selectedConversation; }, [selectedConversation]);

  useEffect(() => {
    fetchConversations();

    let ws = null;
    let stopped = false;
    let pollingInterval = null;

    const startPolling = () => {
      if (pollingInterval) return;
      pollingInterval = setInterval(() => {
        if (!wsConnectedRef.current) fetchConversations();
      }, 15000);
    };

    const stopPolling = () => {
      if (pollingInterval) { clearInterval(pollingInterval); pollingInterval = null; }
    };

    const connectWs = (attempt = 0) => {
      if (stopped) return;
      
      // Reconstrói a URL do WebSocket de forma robusta
      let backendBase = (api.defaults.baseURL || '').replace(/\/api\/?$/, '');
      
      // Se não houver baseURL definida (ex: URL relativa), usa a origem do navegador
      if (!backendBase || backendBase.startsWith('/')) {
        backendBase = window.location.origin;
      }
      
      // Garante que não temos "undefined" na string
      backendBase = backendBase.replace('undefined', '').trim();
      if (!backendBase) backendBase = window.location.origin;

      const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const token = localStorage.getItem('token');
      // Extrai o host corretamente da baseURL do axios ou usa o origin do navegador
      let wsHost = backendBase.replace(/^https?:\/\//, '');
      const wsUrl = `${wsProtocol}://${wsHost}/ws?token=${encodeURIComponent(token || '')}`;

      try {
        ws = new WebSocket(wsUrl);
      } catch (err) {
        console.error('Falha ao criar WebSocket', err);
        wsConnectedRef.current = false;
        startPolling();
        scheduleReconnect(attempt + 1);
        return;
      }

      ws.onopen = () => {
        wsConnectedRef.current = true;
        stopPolling();
        fetchConversations();
      };

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);

          if (data && data.type === 'client_assigned') {
            const clientId = data.client_id;
            const assigned = data.assigned_agent;
            const status = data.status;
            const agentName = data.agent_name || assigned;

            setConversations(prev => prev.map(c => {
              if (c.client.id === clientId) {
                return { ...c, client: { ...c.client, status, assigned_agent: assigned, agent_name: agentName } };
              }
              return c;
            }));

            setSelectedConversation(prev => (prev && prev.client && prev.client.id === clientId)
              ? { ...prev, client: { ...prev.client, status, assigned_agent: assigned, agent_name: agentName } }
              : prev
            );

            showToast(`Atendimento atribuído ao agente ${agentName}`, 'success');
          }

          if (data && data.type === 'new_message') {
            const clientId = data.client_id;
            const newMsg = data.message;

            // Atualiza lista de conversas: move conversa pro topo e atualiza preview
            fetchConversations();

            // Se a conversa aberta é a que recebeu a mensagem, atualiza mensagens
            const currentSel = selectedConversationRef.current;
            if (currentSel && currentSel.client && currentSel.client.id === clientId) {
              setChatMessages(prev => {
                // Evita duplicatas (a mensagem pode ter sido adicionada otimisticamente)
                if (prev.some(m => m.id === newMsg.id)) return prev;
                return [...prev, newMsg];
              });
            } else {
              // Notifica agente de nova mensagem em outra conversa
              if (newMsg && newMsg.sender_type === 'client') {
                showToast(`📩 Nova mensagem de ${clientId}`, 'info');
              }
            }
          }
        } catch (err) {
          console.error('Erro ao processar mensagem WS', err);
        }
      };

      ws.onclose = () => {
        wsConnectedRef.current = false;
        startPolling();
        if (!stopped) scheduleReconnect(attempt + 1);
      };

      ws.onerror = (e) => {
        console.error('WebSocket erro', e);
      };
    };

    const scheduleReconnect = (attempt) => {
      const maxAttempt = 8;
      const t = Math.min(30000, (1000 * Math.pow(2, Math.min(attempt, maxAttempt))));
      setTimeout(() => connectWs(attempt), t);
    };

    startPolling();
    connectWs(0);

    return () => {
      stopped = true;
      wsConnectedRef.current = false;
      stopPolling();
      try { if (ws) ws.close(); } catch (_) {}
    };
  }, []);

  const handleConversationSelect = (conversation) => {
    setSelectedConversation(conversation);
    // Limpa mensagens do chat anterior ao trocar de conversa
    setChatMessages([]);
  };

  const handleSendMessage = async (messageData) => {
    try {
      const response = await api.post('/whatsapp/send', messageData);
      // Retorna o resultado para que o ChatWindow possa atualizar o ID imediamente
      return response.data;
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
      // Atualiza apenas conversa afetada no array `conversations`
      setConversations(prev => prev.map(c => {
        if (c.client.id === clientId) {
          const updated = { ...c, client: { ...c.client, status, assigned_agent: assignedAgent } };
          // também atualiza agent_name quando possível
          if (assignedAgent) {
            // tenta obter username do users já carregado via AdminPanel (não garantido)
            updated.client.agent_name = updated.client.agent_name || null;
          }
          return updated;
        }
        return c;
      }));

      // Atualiza a conversa selecionada se corresponder
      if (selectedConversation && selectedConversation.client.id === clientId) {
        setSelectedConversation(prev => ({
          ...prev,
          client: { ...prev.client, status, assigned_agent: assignedAgent }
        }));
      }
      showToast('Status do cliente atualizado', 'success');
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
        showToast={showToast}
      />
    );
  }

  if (showSettings) {
    return (
      <Settings 
        user={currentUser} 
        onBack={() => setShowSettings(false)} 
      />
    );
  }

  if (showProfile) {
    return (
      <Profile 
        user={currentUser} 
        onBack={() => setShowProfile(false)}
        onUserUpdate={(updatedUser) => {
          setCurrentUser(updatedUser);
          // Atualiza dados do usuário no localStorage
          localStorage.setItem('user', JSON.stringify(updatedUser));
        }}
      />
    );
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50" data-testid="dashboard-container">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-6 right-6 z-50 px-4 py-2 rounded shadow-lg ${toast.type==='success'? 'bg-green-600 text-white' : 'bg-gray-800 text-white'}`}>
          {toast.message}
        </div>
      )}
      <Header 
        user={currentUser} 
        onLogout={logout} 
        onShowAdmin={() => setShowAdminPanel(true)}
        onShowSettings={() => setShowSettings(true)}
        onShowProfile={() => setShowProfile(true)}
      />
      
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
              currentUser={currentUser}
              onSendMessage={handleSendMessage}
              onStatusUpdate={handleClientStatusUpdate}
              showToast={showToast}
              externalMessages={chatMessages}
              updateConversationInList={(clientId, status, assignedAgent, name) => {
                setConversations(prev => prev.map(c => {
                  if (c.client.id !== clientId) return c;
                  const updated = { ...c, client: { ...c.client, status, assigned_agent: assignedAgent } };
                  if (name !== undefined) updated.client.name = name;
                  return updated;
                }));
                if (selectedConversation && selectedConversation.client.id === clientId) {
                  setSelectedConversation(prev => {
                    if (!prev) return prev;
                    const updated = { ...prev, client: { ...prev.client, status, assigned_agent: assignedAgent } };
                    if (name !== undefined) updated.client.name = name;
                    return updated;
                  });
                }
              }}
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