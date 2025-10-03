import React, { useState, useEffect } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Badge } from './ui/badge';
import { api } from '../App';

const AdminPanel = ({ user, onBack }) => {
  const [users, setUsers] = useState([]);
  const [newUser, setNewUser] = useState({
    username: '',
    email: '',
    password: '',
    role: 'agent'
  });
  
  const [agentPerformance, setAgentPerformance] = useState([]);
  const [serviceMetrics, setServiceMetrics] = useState([]);
  
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', content: '' });

  const getRoleBadge = (role) => {
    switch (role) {
      case 'admin':
        return <Badge className="bg-purple-100 text-purple-800">Admin</Badge>;
      case 'agent':
        return <Badge className="bg-blue-100 text-blue-800">Agente</Badge>;
      default:
        return <Badge className="bg-gray-100 text-gray-800">{role}</Badge>;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'online':
        return 'bg-green-100 text-green-800';
      case 'busy':
        return 'bg-blue-100 text-blue-800';
      case 'paused':
        return 'bg-yellow-100 text-yellow-800';
      case 'offline':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'online':
        return 'Online';
      case 'busy':
        return 'Em atendimento';
      case 'paused':
        return 'Em pausa';
      case 'offline':
        return 'Offline';
      default:
        return status;
    }
  };

  useEffect(() => {
    fetchUsers();
    fetchAgentPerformance();
    fetchServiceMetrics();
  }, []);

  const fetchUsers = async () => {
    try {
      const response = await api.get('/admin/users');
      setUsers(response.data);
    } catch (error) {
      console.error('Erro ao buscar usuários:', error);
    }
  };

  const fetchAgentPerformance = async () => {
    try {
      const response = await api.get('/admin/agents-performance');
      setAgentPerformance(response.data);
    } catch (error) {
      console.error('Erro ao buscar performance:', error);
    }
  };

  const fetchServiceMetrics = async () => {
    try {
      const response = await api.get('/admin/service-metrics');
      setServiceMetrics(response.data);
    } catch (error) {
      console.error('Erro ao buscar métricas:', error);
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      await api.post('/auth/register', newUser);
      setMessage({ type: 'success', content: 'Usuário criado com sucesso!' });
      setNewUser({ username: '', email: '', password: '', role: 'agent' });
      await fetchUsers();
      setTimeout(() => setMessage({ type: '', content: '' }), 3000);
    } catch (error) {
      setMessage({ type: 'error', content: error.response?.data?.detail || 'Erro ao criar usuário.' });
      console.error('Erro:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteUser = async (userId) => {
    if (!window.confirm('Tem certeza que deseja excluir este usuário?')) return;
    
    try {
      await api.delete(`/admin/users/${userId}`);
      setMessage({ type: 'success', content: 'Usuário excluído com sucesso!' });
      await fetchUsers();
      setTimeout(() => setMessage({ type: '', content: '' }), 3000);
    } catch (error) {
      setMessage({ type: 'error', content: 'Erro ao excluir usuário.' });
      console.error('Erro:', error);
    }
  };

  if (user.role !== 'admin') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Card className="p-8 text-center">
          <h2 className="text-2xl font-bold text-red-600 mb-4">Acesso Negado</h2>
          <p className="text-gray-600 mb-4">Apenas administradores podem acessar este painel.</p>
          <Button onClick={onBack}>Voltar ao Dashboard</Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6" data-testid="admin-panel">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Painel Administrativo</h1>
            <p className="text-gray-600">Configurações do sistema e gerenciamento</p>
          </div>
          <Button onClick={onBack} variant="outline" data-testid="back-to-dashboard-btn">
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Voltar ao Dashboard
          </Button>
        </div>

        {message.content && (
          <div className={`p-4 mb-6 rounded-lg ${
            message.type === 'success' ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'
          }`} data-testid="admin-message">
            {message.content}
          </div>
        )}

        <Tabs defaultValue="performance" className="space-y-6">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="performance" data-testid="performance-tab">Performance</TabsTrigger>
            <TabsTrigger value="users" data-testid="users-tab">Gerenciar Usuários</TabsTrigger>
          </TabsList>

          <TabsContent value="performance">
            <div className="space-y-6">
              {/* Agent Performance Cards */}
              <Card className="p-6">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-xl font-semibold">Performance dos Atendentes</h2>
                    <p className="text-gray-600">Métricas de desempenho e status dos agentes</p>
                  </div>
                  <Button onClick={fetchAgentPerformance} variant="outline" data-testid="refresh-performance">
                    🔄 Atualizar
                  </Button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {agentPerformance.map((agent) => (
                    <Card key={agent.agent_id} className="p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center space-x-3">
                          <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center text-white font-medium text-sm">
                            {agent.agent_name.charAt(0).toUpperCase()}
                          </div>
                          <span className="font-medium">{agent.agent_name}</span>
                        </div>
                        <Badge className={getStatusColor(agent.status)}>
                          {getStatusText(agent.status)}
                        </Badge>
                      </div>
                      
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-600">Total conversas:</span>
                          <span className="font-medium">{agent.total_conversations}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Finalizadas hoje:</span>
                          <span className="font-medium">{agent.conversations_finished_today}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Tempo médio:</span>
                          <span className="font-medium">{agent.avg_response_time_minutes}min</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Última atividade:</span>
                          <span className="text-xs text-gray-500">
                            {new Date(agent.last_activity).toLocaleString('pt-BR')}
                          </span>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              </Card>

              {/* Service Metrics Table */}
              <Card className="p-6">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-xl font-semibold">Histórico de Atendimentos</h2>
                    <p className="text-gray-600">Últimos 30 dias - Atendimentos finalizados</p>
                  </div>
                  <Button onClick={fetchServiceMetrics} variant="outline" data-testid="refresh-metrics">
                    🔄 Atualizar
                  </Button>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left p-2">Cliente</th>
                        <th className="text-left p-2">Atendente</th>
                        <th className="text-left p-2">Duração</th>
                        <th className="text-left p-2">Iniciado</th>
                        <th className="text-left p-2">Finalizado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {serviceMetrics.slice(0, 10).map((metric) => (
                        <tr key={metric.conversation_id} className="border-b hover:bg-gray-50">
                          <td className="p-2">
                            <div>
                              <div className="font-medium">{metric.client_name || 'Cliente anônimo'}</div>
                              <div className="text-xs text-gray-600">{metric.client_phone}</div>
                            </div>
                          </td>
                          <td className="p-2 font-medium">{metric.agent_name}</td>
                          <td className="p-2">
                            {metric.service_duration_minutes ? (
                              <span className={`px-2 py-1 rounded text-xs ${
                                metric.service_duration_minutes < 10 
                                  ? 'bg-green-100 text-green-800' 
                                  : metric.service_duration_minutes < 30 
                                    ? 'bg-yellow-100 text-yellow-800' 
                                    : 'bg-red-100 text-red-800'
                              }`}>
                                {metric.service_duration_minutes.toFixed(1)}min
                              </span>
                            ) : '-'}
                          </td>
                          <td className="p-2 text-xs text-gray-600">
                            {new Date(metric.started_at).toLocaleString('pt-BR')}
                          </td>
                          <td className="p-2 text-xs text-gray-600">
                            {metric.finished_at ? new Date(metric.finished_at).toLocaleString('pt-BR') : '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  
                  {serviceMetrics.length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      Nenhum atendimento finalizado encontrado
                    </div>
                  )}
                </div>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="users">
            <div className="space-y-6">
              <Card className="p-6">
                <h2 className="text-xl font-semibold mb-4">Criar Novo Usuário</h2>
                <form onSubmit={handleCreateUser} className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="new_username">Nome de Usuário</Label>
                      <Input
                        id="new_username"
                        value={newUser.username}
                        onChange={(e) => setNewUser({...newUser, username: e.target.value})}
                        placeholder="Digite o nome de usuário"
                        required
                        data-testid="new-user-username"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="new_email">Email</Label>
                      <Input
                        id="new_email"
                        type="email"
                        value={newUser.email}
                        onChange={(e) => setNewUser({...newUser, email: e.target.value})}
                        placeholder="Digite o email"
                        required
                        data-testid="new-user-email"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="new_password">Senha</Label>
                      <Input
                        id="new_password"
                        type="password"
                        value={newUser.password}
                        onChange={(e) => setNewUser({...newUser, password: e.target.value})}
                        placeholder="Digite a senha"
                        required
                        data-testid="new-user-password"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="new_role">Nível</Label>
                      <select
                        id="new_role"
                        value={newUser.role}
                        onChange={(e) => setNewUser({...newUser, role: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md"
                        data-testid="new-user-role"
                      >
                        <option value="agent">Agente</option>
                        <option value="admin">Administrador</option>
                      </select>
                    </div>
                  </div>

                  <Button type="submit" disabled={loading} data-testid="create-user-btn">
                    {loading ? 'Criando...' : 'Criar Usuário'}
                  </Button>
                </form>
              </Card>

              <Card className="p-6">
                <h2 className="text-xl font-semibold mb-4">Usuários Cadastrados</h2>
                <div className="space-y-3" data-testid="users-list">
                  {users.map((userItem) => (
                    <div key={userItem.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                      <div className="flex items-center space-x-3">
                        <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center text-white font-medium text-sm">
                          {userItem.username.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <div className="font-medium">{userItem.username}</div>
                          <div className="text-sm text-gray-600">{userItem.email}</div>
                        </div>
                        <Badge className={userItem.role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'}>
                          {userItem.role === 'admin' ? 'Admin' : 'Agente'}
                        </Badge>
                      </div>
                      <Button 
                        onClick={() => handleDeleteUser(userItem.id)} 
                        variant="destructive" 
                        size="sm"
                        disabled={userItem.id === user.id}
                        data-testid={`delete-user-${userItem.username}`}
                      >
                        🗑️ Excluir
                      </Button>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default AdminPanel;