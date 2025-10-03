import React, { useState, useEffect } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Badge } from './ui/badge';
import { api } from '../App';

const Profile = ({ user, onBack, onUserUpdate }) => {
  const [profileData, setProfileData] = useState({
    username: user.username || '',
    email: user.email || '',
    full_name: user.full_name || ''
  });
  
  const [passwordData, setPasswordData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  });
  
  const [allUsers, setAllUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', content: '' });

  useEffect(() => {
    if (user.role === 'admin') {
      fetchAllUsers();
    }
  }, [user.role]);

  const fetchAllUsers = async () => {
    try {
      const response = await api.get('/admin/users');
      setAllUsers(response.data);
    } catch (error) {
      console.error('Erro ao buscar usuários:', error);
    }
  };

  const handleProfileUpdate = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const response = await api.put('/profile/update', profileData);
      setMessage({ type: 'success', content: 'Perfil atualizado com sucesso!' });
      onUserUpdate && onUserUpdate(response.data);
      setTimeout(() => setMessage({ type: '', content: '' }), 3000);
    } catch (error) {
      setMessage({ type: 'error', content: error.response?.data?.detail || 'Erro ao atualizar perfil.' });
      setTimeout(() => setMessage({ type: '', content: '' }), 3000);
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordUpdate = async (e) => {
    e.preventDefault();
    
    if (passwordData.new_password !== passwordData.confirm_password) {
      setMessage({ type: 'error', content: 'A confirmação de senha não confere.' });
      setTimeout(() => setMessage({ type: '', content: '' }), 3000);
      return;
    }
    
    if (passwordData.new_password.length < 6) {
      setMessage({ type: 'error', content: 'A nova senha deve ter pelo menos 6 caracteres.' });
      setTimeout(() => setMessage({ type: '', content: '' }), 3000);
      return;
    }

    setLoading(true);
    
    try {
      await api.put('/profile/change-password', {
        current_password: passwordData.current_password,
        new_password: passwordData.new_password
      });
      setMessage({ type: 'success', content: 'Senha alterada com sucesso!' });
      setPasswordData({ current_password: '', new_password: '', confirm_password: '' });
      setTimeout(() => setMessage({ type: '', content: '' }), 3000);
    } catch (error) {
      setMessage({ type: 'error', content: error.response?.data?.detail || 'Erro ao alterar senha.' });
      setTimeout(() => setMessage({ type: '', content: '' }), 3000);
    } finally {
      setLoading(false);
    }
  };

  const handleUserUpdate = async (userId, userData) => {
    setLoading(true);
    try {
      await api.put(`/admin/users/${userId}`, userData);
      setMessage({ type: 'success', content: 'Usuário atualizado com sucesso!' });
      await fetchAllUsers();
      setTimeout(() => setMessage({ type: '', content: '' }), 3000);
    } catch (error) {
      setMessage({ type: 'error', content: 'Erro ao atualizar usuário.' });
      setTimeout(() => setMessage({ type: '', content: '' }), 3000);
    } finally {
      setLoading(false);
    }
  };

  const getRoleBadge = (role) => {
    switch (role) {
      case 'admin':
        return <Badge className="bg-purple-100 text-purple-800">Administrador</Badge>;
      case 'agent':
        return <Badge className="bg-blue-100 text-blue-800">Agente</Badge>;
      default:
        return <Badge className="bg-gray-100 text-gray-800">{role}</Badge>;
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'online':
        return <Badge className="bg-green-100 text-green-800">Online</Badge>;
      case 'busy':
        return <Badge className="bg-blue-100 text-blue-800">Em atendimento</Badge>;
      case 'paused':
        return <Badge className="bg-yellow-100 text-yellow-800">Em pausa</Badge>;
      case 'offline':
        return <Badge className="bg-gray-100 text-gray-800">Offline</Badge>;
      default:
        return <Badge className="bg-gray-100 text-gray-800">{status || 'Offline'}</Badge>;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6" data-testid="profile-panel">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Perfil do Usuário</h1>
            <p className="text-gray-600">Gerencie suas informações pessoais</p>
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
          }`} data-testid="profile-message">
            {message.content}
          </div>
        )}

        <Tabs defaultValue="profile" className="space-y-6">
          <TabsList className={`grid w-full ${user.role === 'admin' ? 'grid-cols-3' : 'grid-cols-2'}`}>
            <TabsTrigger value="profile" data-testid="profile-tab">Meu Perfil</TabsTrigger>
            <TabsTrigger value="password" data-testid="password-tab">Alterar Senha</TabsTrigger>
            {user.role === 'admin' && (
              <TabsTrigger value="users" data-testid="all-users-tab">Todos os Usuários</TabsTrigger>
            )}
          </TabsList>

          <TabsContent value="profile">
            <Card className="p-6">
              <h2 className="text-xl font-semibold mb-6">Informações Pessoais</h2>
              
              <form onSubmit={handleProfileUpdate} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="full_name">Nome Completo</Label>
                    <Input
                      id="full_name"
                      value={profileData.full_name}
                      onChange={(e) => setProfileData({...profileData, full_name: e.target.value})}
                      placeholder="Digite seu nome completo"
                      data-testid="profile-full-name"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="username">Nome de Usuário</Label>
                    <Input
                      id="username"
                      value={profileData.username}
                      onChange={(e) => setProfileData({...profileData, username: e.target.value})}
                      placeholder="Digite seu nome de usuário"
                      required
                      data-testid="profile-username"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input
                      id="email"
                      type="email"
                      value={profileData.email}
                      onChange={(e) => setProfileData({...profileData, email: e.target.value})}
                      placeholder="Digite seu email"
                      required
                      data-testid="profile-email"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Nível de Acesso</Label>
                    <div className="pt-2">
                      {getRoleBadge(user.role)}
                    </div>
                    <p className="text-xs text-gray-500">Apenas administradores podem alterar níveis de acesso</p>
                  </div>
                </div>

                <div className="pt-4 border-t">
                  <Button type="submit" disabled={loading} data-testid="update-profile-btn">
                    {loading ? 'Atualizando...' : 'Atualizar Perfil'}
                  </Button>
                </div>
              </form>
            </Card>
          </TabsContent>

          <TabsContent value="password">
            <Card className="p-6">
              <h2 className="text-xl font-semibold mb-6">Alterar Senha</h2>
              
              <form onSubmit={handlePasswordUpdate} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="current_password">Senha Atual</Label>
                    <Input
                      id="current_password"
                      type="password"
                      value={passwordData.current_password}
                      onChange={(e) => setPasswordData({...passwordData, current_password: e.target.value})}
                      placeholder="Digite sua senha atual"
                      required
                      data-testid="current-password"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="new_password">Nova Senha</Label>
                    <Input
                      id="new_password"
                      type="password"
                      value={passwordData.new_password}
                      onChange={(e) => setPasswordData({...passwordData, new_password: e.target.value})}
                      placeholder="Digite a nova senha (min. 6 caracteres)"
                      required
                      minLength={6}
                      data-testid="new-password"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="confirm_password">Confirmar Nova Senha</Label>
                    <Input
                      id="confirm_password"
                      type="password"
                      value={passwordData.confirm_password}
                      onChange={(e) => setPasswordData({...passwordData, confirm_password: e.target.value})}
                      placeholder="Confirme a nova senha"
                      required
                      data-testid="confirm-password"
                    />
                  </div>
                </div>

                <div className="pt-4 border-t">
                  <Button type="submit" disabled={loading} data-testid="change-password-btn">
                    {loading ? 'Alterando...' : 'Alterar Senha'}
                  </Button>
                </div>
              </form>
            </Card>
          </TabsContent>

          {user.role === 'admin' && (
            <TabsContent value="users">
              <Card className="p-6">
                <h2 className="text-xl font-semibold mb-6">Gerenciar Todos os Usuários</h2>
                
                <div className="space-y-4">
                  {allUsers.map((userItem) => (
                    <div key={userItem.id} className="p-4 bg-gray-50 rounded-lg">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center space-x-3">
                          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-full flex items-center justify-center text-white font-medium">
                            {(userItem.full_name || userItem.username).charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <h4 className="font-medium">{userItem.full_name || userItem.username}</h4>
                            <p className="text-sm text-gray-600">@{userItem.username}</p>
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          {getRoleBadge(userItem.role)}
                          {getStatusBadge(userItem.status)}
                        </div>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                        <div>
                          <strong>Email:</strong> {userItem.email}
                        </div>
                        <div>
                          <strong>Criado em:</strong> {new Date(userItem.created_at).toLocaleDateString('pt-BR')}
                        </div>
                        <div>
                          <strong>Última atividade:</strong> {
                            userItem.last_activity 
                              ? new Date(userItem.last_activity).toLocaleString('pt-BR')
                              : 'Nunca'
                          }
                        </div>
                      </div>
                    </div>
                  ))}
                  
                  {allUsers.length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      Nenhum usuário encontrado
                    </div>
                  )}
                </div>
              </Card>
            </TabsContent>
          )}
        </Tabs>
      </div>
    </div>
  );
};

export default Profile;