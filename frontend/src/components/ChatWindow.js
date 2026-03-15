import React, { useState, useEffect, useRef } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from './ui/dropdown-menu';
import { api } from '../App';
import { getAuth, reauthenticateWithCredential, EmailAuthProvider } from 'firebase/auth';

// ─── Modal de Confirmação de Senha ─────────────────────────────────────────
const PasswordConfirmModal = ({ onConfirm, onCancel }) => {
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!password.trim()) { setError('Digite sua senha.'); return; }
    setLoading(true);
    setError('');
    try {
      const auth = getAuth();
      const user = auth.currentUser;
      if (!user || !user.email) throw new Error('Usuário não autenticado.');
      const credential = EmailAuthProvider.credential(user.email, password);
      await reauthenticateWithCredential(user, credential);
      onConfirm();
    } catch (err) {
      const msg = err.code === 'auth/wrong-password' || err.code === 'auth/invalid-credential'
        ? 'Senha incorreta. Tente novamente.'
        : 'Erro ao confirmar. Verifique sua senha.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-sm mx-4 space-y-4">
        <div className="text-center">
          <div className="text-4xl mb-2">🔐</div>
          <h2 className="text-lg font-bold text-gray-800">Confirmação necessária</h2>
          <p className="text-sm text-gray-500 mt-1">Digite sua senha para assumir o atendimento.</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="relative">
            <input
              ref={inputRef}
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Sua senha"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              tabIndex={-1}
            >
              {showPassword ? '🙈' : '👁️'}
            </button>
          </div>
          {error && <p className="text-xs text-red-600 font-medium">{error}</p>}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="flex-1 px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-2 text-sm bg-green-500 text-white rounded-lg hover:bg-green-600 transition disabled:opacity-60"
            >
              {loading ? 'Verificando...' : 'Confirmar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ─── Modal de Atribuição de Agente (Admin) ──────────────────────────────────
const AssignAgentModal = ({ clientName, onAssign, onCancel }) => {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingAgents, setLoadingAgents] = useState(true);

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const res = await api.get('/admin/users');
        const filtered = res.data.filter(u => u.role === 'agent' || u.role === 'admin');
        setAgents(filtered);
      } catch (e) {
        console.error('Erro ao buscar agentes:', e);
      } finally {
        setLoadingAgents(false);
      }
    };
    fetchAgents();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedAgent) return;
    setLoading(true);
    try {
      await onAssign(selectedAgent);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-sm mx-4 space-y-4">
        <div className="text-center">
          <div className="text-4xl mb-2">👤</div>
          <h2 className="text-lg font-bold text-gray-800">Atribuir Atendimento</h2>
          <p className="text-sm text-gray-500 mt-1">
            Escolha o agente que vai assumir <strong>{clientName || 'este cliente'}</strong>.
          </p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          {loadingAgents ? (
            <div className="flex justify-center py-3">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-green-500"></div>
            </div>
          ) : (
            <select
              value={selectedAgent}
              onChange={e => setSelectedAgent(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            >
              <option value="">-- Selecione um agente --</option>
              {agents.map(a => (
                <option key={a.id} value={a.id}>
                  {a.full_name || a.username} ({a.role})
                </option>
              ))}
            </select>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="flex-1 px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading || !selectedAgent || loadingAgents}
              className="flex-1 px-4 py-2 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition disabled:opacity-60"
            >
              {loading ? 'Atribuindo...' : '✅ Atribuir'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ─── ChatWindow principal ───────────────────────────────────────────────────
const ChatWindow = ({ conversation, currentUser, onSendMessage, onStatusUpdate, showToast, updateConversationInList, externalMessages }) => {
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [accepting, setAccepting] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [clientName, setClientName] = useState(conversation?.client?.name || '');
  const [savingName, setSavingName] = useState(false);

  // Modais
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [showAssignModal, setShowAssignModal] = useState(false);

  const messagesEndRef = useRef(null);
  const messageIdsRef = useRef(new Set());
  const nameInputRef = useRef(null);

  const isAdmin = currentUser?.role === 'admin';

  useEffect(() => {
    const fetchMessages = async () => {
      if (!conversation?.client?.id) return;
      setLoading(true);
      try {
        const response = await api.get(`/clients/${conversation.client.id}/messages`);
        const fetched = response.data;
        messageIdsRef.current = new Set(fetched.map(m => m.id));
        setMessages(fetched);
      } catch (error) {
        console.error('Erro ao buscar mensagens:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchMessages();
  }, [conversation?.client?.id]);

  useEffect(() => {
    setClientName(conversation?.client?.name || '');
    setEditingName(false);
  }, [conversation?.client?.id, conversation?.client?.name]);

  useEffect(() => {
    if (editingName && nameInputRef.current) {
      nameInputRef.current.focus();
      nameInputRef.current.select();
    }
  }, [editingName]);

  useEffect(() => {
    if (!externalMessages || externalMessages.length === 0) return;
    setMessages(prev => {
      const existingIds = new Set(prev.map(m => m.id));
      const toAdd = externalMessages.filter(m => !existingIds.has(m.id));
      if (toAdd.length === 0) return prev;
      const updated = [...prev, ...toAdd];
      messageIdsRef.current = new Set(updated.map(m => m.id));
      return updated;
    });
  }, [externalMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || sendingMessage) return;
    setSendingMessage(true);
    const content = newMessage.trim();
    setNewMessage('');
    const tempId = `temp-${Date.now()}`;
    const tempMessage = {
      id: tempId,
      client_id: conversation.client.id,
      sender_type: 'agent',
      sender_id: currentUser.id,
      content,
      timestamp: new Date().toISOString()
    };
    messageIdsRef.current.add(tempId);
    setMessages(prev => [...prev, tempMessage]);
    try {
      const messageData = {
        client_id: conversation.client.id,
        sender_type: 'agent',
        sender_id: currentUser.id,
        content
      };
      const result = await onSendMessage(messageData);
      if (result && result.message_id) {
        setMessages(prev => prev.map(m => m.id === tempId ? { ...m, id: result.message_id } : m));
        messageIdsRef.current.delete(tempId);
        messageIdsRef.current.add(result.message_id);
      }
    } catch (error) {
      console.error('Erro ao enviar mensagem:', error);
      setMessages(prev => prev.filter(m => m.id !== tempId));
      messageIdsRef.current.delete(tempId);
      if (typeof showToast === 'function') showToast('Erro ao enviar mensagem. Verifique a configuração da integração.', 'error');
    } finally {
      setSendingMessage(false);
    }
  };

  const handleSaveName = async () => {
    const name = clientName.trim();
    if (name === (conversation?.client?.name || '')) { setEditingName(false); return; }
    setSavingName(true);
    try {
      await api.put(`/clients/${conversation.client.id}`, { name });
      if (typeof updateConversationInList === 'function') {
        updateConversationInList(conversation.client.id, conversation.client.status, conversation.client.assigned_agent, name);
      }
      if (typeof showToast === 'function') showToast('Nome salvo com sucesso!', 'success');
    } catch (err) {
      console.error('Erro ao salvar nome:', err);
      if (typeof showToast === 'function') showToast('Erro ao salvar nome.', 'error');
      setClientName(conversation?.client?.name || '');
    } finally {
      setSavingName(false);
      setEditingName(false);
    }
  };

  const handleStatusChange = async (newStatus, assignedAgent = null) => {
    try {
      await onStatusUpdate(conversation.client.id, newStatus, assignedAgent);
    } catch (error) {
      console.error('Erro ao alterar status:', error);
    }
  };

  // Aceitar atendimento — admin precisa confirmar senha primeiro
  const handleAcceptService = () => {
    if (accepting) return;
    if (isAdmin) {
      setShowPasswordModal(true);
    } else {
      doAcceptService();
    }
  };

  const doAcceptService = async () => {
    setAccepting(true);
    try {
      if (typeof updateConversationInList === 'function') {
        updateConversationInList(conversation.client.id, 'human', currentUser.id);
      }
      await api.put(`/clients/${conversation.client.id}/accept-service`);
      try {
        if (typeof onStatusUpdate === 'function') {
          await onStatusUpdate(conversation.client.id, 'human', currentUser.id);
        }
      } catch (err) {
        console.error('Falha ao atualizar status no dashboard:', err);
      }
      try {
        const msgs = await api.get(`/clients/${conversation.client.id}/messages`);
        setMessages(msgs.data);
      } catch (err) {
        console.error('Erro ao buscar mensagens após aceitar:', err);
      }
      if (typeof showToast === 'function') showToast('Você assumiu o atendimento', 'success');
    } catch (error) {
      console.error('Erro ao aceitar atendimento:', error);
      const st = error?.response?.status;
      const detail = error?.response?.data?.detail || '';
      if (st === 409) {
        if (detail.includes(currentUser.id)) {
          if (typeof showToast === 'function') showToast('Você já está atendendo este cliente', 'success');
          try { const msgs = await api.get(`/clients/${conversation.client.id}/messages`); setMessages(msgs.data); } catch (_) {}
          return;
        }
        if (typeof showToast === 'function') showToast(detail || 'Este atendimento já foi assumido por outro agente.', 'error');
      } else if (!error?.response) {
        if (typeof showToast === 'function') showToast('Erro de rede ao assumir atendimento.', 'error');
      } else {
        if (typeof showToast === 'function') showToast('Erro ao aceitar atendimento.', 'error');
      }
      if (typeof updateConversationInList === 'function') {
        try { updateConversationInList(conversation.client.id, conversation.client.status || 'bot', conversation.client.assigned_agent || null); } catch (_) {}
      }
    } finally {
      setAccepting(false);
    }
  };

  const handleFinishService = async () => {
    if (!window.confirm('Tem certeza que deseja finalizar este atendimento?')) return;
    try {
      await api.put(`/clients/${conversation.client.id}/finish-service`);
      if (typeof updateConversationInList === 'function') updateConversationInList(conversation.client.id, 'finished', null);
      if (typeof onStatusUpdate === 'function') await onStatusUpdate(conversation.client.id, 'finished', null);
      if (typeof showToast === 'function') showToast('Atendimento finalizado com sucesso!', 'success');
    } catch (error) {
      console.error('Erro ao finalizar atendimento:', error);
      if (typeof showToast === 'function') showToast('Erro ao finalizar atendimento.', 'error');
    }
  };

  // Admin atribuir para agente específico
  const handleAssignToAgent = async (agentId) => {
    try {
      await api.post(`/admin/assign-client/${conversation.client.id}`, { agent_id: agentId });
      setShowAssignModal(false);
      if (typeof updateConversationInList === 'function') updateConversationInList(conversation.client.id, 'human', agentId);
      if (typeof onStatusUpdate === 'function') await onStatusUpdate(conversation.client.id, 'human', agentId);
      if (typeof showToast === 'function') showToast('Atendimento atribuído com sucesso!', 'success');
    } catch (error) {
      console.error('Erro ao atribuir agente:', error);
      const detail = error?.response?.data?.detail || 'Erro ao atribuir agente.';
      if (typeof showToast === 'function') showToast(detail, 'error');
    }
  };

  const getMessageBubbleStyle = (senderType) => {
    switch (senderType) {
      case 'client': return 'bg-white border border-gray-200 text-gray-900 rounded-tr-2xl rounded-tl-2xl rounded-br-2xl';
      case 'agent': return 'bg-green-500 text-white rounded-tl-2xl rounded-tr-2xl rounded-bl-2xl ml-auto';
      case 'bot': return 'bg-blue-600 text-white rounded-tl-2xl rounded-tr-2xl rounded-bl-2xl ml-auto shadow-sm';
      default: return 'bg-gray-100 text-gray-900 rounded-lg';
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'bot': return 'bg-green-100 text-green-800';
      case 'human': return 'bg-blue-100 text-blue-800';
      case 'waiting': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'bot': return 'BOT';
      case 'human': return 'HUMANO';
      case 'waiting': return 'AGUARDANDO';
      default: return status?.toUpperCase() || '';
    }
  };

  const formatTime = (timestamp) => new Date(timestamp).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });

  if (!conversation) return null;

  return (
    <div className="flex flex-col h-full bg-white" data-testid="chat-window">

      {/* Modais */}
      {showPasswordModal && (
        <PasswordConfirmModal
          onConfirm={() => { setShowPasswordModal(false); doAcceptService(); }}
          onCancel={() => setShowPasswordModal(false)}
        />
      )}
      {showAssignModal && (
        <AssignAgentModal
          clientName={clientName || conversation.client.phone_number}
          onAssign={handleAssignToAgent}
          onCancel={() => setShowAssignModal(false)}
        />
      )}

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
            {editingName ? (
              <div className="flex items-center space-x-1">
                <input
                  ref={nameInputRef}
                  type="text"
                  value={clientName}
                  onChange={e => setClientName(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleSaveName(); if (e.key === 'Escape') { setClientName(conversation?.client?.name || ''); setEditingName(false); } }}
                  className="text-sm font-semibold text-gray-900 border border-green-400 rounded px-2 py-0.5 w-40 focus:outline-none focus:ring-1 focus:ring-green-500"
                  placeholder="Nome do cliente"
                  maxLength={60}
                />
                <button onClick={handleSaveName} disabled={savingName} className="text-green-600 hover:text-green-800 disabled:opacity-50 text-sm font-bold px-1" title="Salvar nome">
                  {savingName ? '...' : '✓'}
                </button>
                <button onClick={() => { setClientName(conversation?.client?.name || ''); setEditingName(false); }} className="text-gray-400 hover:text-gray-600 text-sm px-1" title="Cancelar">✕</button>
              </div>
            ) : (
              <div className="flex items-center space-x-1 group">
                <h3 className="font-semibold text-gray-900" data-testid="chat-client-name">{clientName || conversation.client.phone_number}</h3>
                <button onClick={() => setEditingName(true)} className="text-gray-300 hover:text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity" title="Editar nome do cliente">✏️</button>
              </div>
            )}
            <p className="text-xs text-gray-500">{conversation.client.phone_number}</p>
          </div>
          <Badge className={getStatusColor(conversation.client.status)}>{getStatusText(conversation.client.status)}</Badge>
        </div>

        <div className="flex items-center space-x-2 flex-wrap gap-1">
          {/* Botão Aceitar Atendimento:
               - Status 'bot' ou 'waiting': qualquer agente pode aceitar
               - Status 'human': só admin pode aceitar (via confirmação de senha) */}
          {(
            conversation.client.status === 'waiting' ||
            conversation.client.status === 'bot' ||
            (conversation.client.status === 'human' && isAdmin)
          ) && (
            <Button
              onClick={handleAcceptService}
              className="bg-green-500 hover:bg-green-600 text-white"
              size="sm"
              disabled={accepting}
              data-testid="accept-service-btn"
            >
              {accepting ? '⏳' : '✅'} {conversation.client.status === 'human' ? 'Assumir do Agente' : 'Aceitar Atendimento'}
            </Button>
          )}

          {/* Botão Atribuir para Agente (apenas admin) */}
          {isAdmin && (
            <Button
              onClick={() => setShowAssignModal(true)}
              className="bg-blue-500 hover:bg-blue-600 text-white"
              size="sm"
              data-testid="assign-agent-btn"
            >
              👤 Atribuir Agente
            </Button>
          )}

          {/* Botão Finalizar */}
          {conversation.client.assigned_agent === currentUser.id && conversation.client.status === 'human' && (
            <Button onClick={handleFinishService} variant="outline" size="sm" data-testid="finish-service-btn">
              🏁 Finalizar Atendimento
            </Button>
          )}

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
              <DropdownMenuItem onClick={() => handleStatusChange('bot')} data-testid="status-bot-option">
                <div className="w-3 h-3 bg-green-500 rounded-full mr-2"></div>
                Atendimento por BOT
              </DropdownMenuItem>
              {/* Opção Assumir — esconde para agentes quando já está em atendimento humano */}
              {(conversation.client.status !== 'human' || isAdmin) && (
                <DropdownMenuItem onClick={() => handleAcceptService()} data-testid="status-human-option">
                  <div className="w-3 h-3 bg-blue-500 rounded-full mr-2"></div>
                  Assumir Atendimento
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onClick={() => handleStatusChange('waiting')} data-testid="status-waiting-option">
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
              className={`flex ${['agent', 'bot'].includes(message.sender_type) ? 'justify-end' : 'justify-start'}`}
              data-testid={`message-${index}`}
            >
              <div className={`max-w-xs lg:max-w-md px-4 py-2 ${getMessageBubbleStyle(message.sender_type)}`}>
                {message.message_type === 'image' && message.media_metadata?.url && (
                  <div className="mb-2">
                    <img src={message.media_metadata.url} alt={message.content} className="rounded-lg max-w-full h-auto cursor-pointer hover:opacity-90 transition-opacity" onClick={() => window.open(message.media_metadata.url, '_blank')} />
                  </div>
                )}
                {message.message_type === 'document' && message.media_metadata?.url && (
                  <div className="mb-2 p-3 bg-white/10 rounded-lg flex items-center space-x-3 border border-white/20">
                    <div className="bg-white/20 p-2 rounded">
                      <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <div className="flex-1 overflow-hidden">
                      <p className="text-sm font-medium truncate text-white">{message.media_metadata.filename || 'Documento'}</p>
                      <a href={message.media_metadata.url} target="_blank" rel="noopener noreferrer" className="text-xs text-white underline hover:opacity-80">Visualizar Arquivo</a>
                    </div>
                  </div>
                )}
                {message.message_type === 'sticker' && message.media_metadata?.url && (
                  <div className="mb-2"><img src={message.media_metadata.url} alt="Sticker" className="w-32 h-32 object-contain" /></div>
                )}
                <p className="text-sm leading-relaxed">{message.content}</p>
                <div className={`text-xs mt-1 ${['agent', 'bot'].includes(message.sender_type) ? 'text-white/80' : 'text-gray-500'}`}>
                  {formatTime(message.timestamp)}
                  {message.sender_type === 'bot' && <span className="ml-2 font-bold text-white uppercase" style={{fontSize: '9px'}}>🤖 BOT</span>}
                </div>
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Message Input */}
      <div className="p-4 border-t border-gray-200 bg-white">
        {(conversation.client.status === 'bot' || conversation.client.status === 'finished') ? (
          <div className="flex items-center justify-center py-3 px-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <span className="text-sm text-yellow-700">
              {conversation.client.status === 'finished'
                ? '🏁 Atendimento finalizado. Não é possível enviar novas mensagens.'
                : '🤖 Conversa em modo BOT. Clique em "Aceitar Atendimento" para poder enviar mensagens.'
              }
            </span>
          </div>
        ) : (
          <form onSubmit={handleSendMessage} className="flex space-x-3">
            <Input
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              placeholder="Digite sua mensagem..."
              className="flex-1"
              disabled={sendingMessage}
              data-testid="message-input"
              onKeyPress={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(e); } }}
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
        )}
        <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
          <span>Pressione Enter para enviar, Shift+Enter para nova linha</span>
          <span>
            {conversation.client.assigned_agent && (
              `Responsável: ${conversation.client.agent_name || conversation.client.assigned_agent}`
            )}
          </span>
        </div>
      </div>
    </div>
  );
};

export default ChatWindow;