import React, { useState, useEffect } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { api } from '../App';

const Settings = ({ user, onBack }) => {
  const [whatsappConfig, setWhatsappConfig] = useState({
    api_key: '',
    phone_number_id: '',
    business_account_id: '',
    webhook_verify_token: '',
    webhook_url: '',
    access_token: ''
  });
  
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', content: '' });

  useEffect(() => {
    fetchWhatsAppConfig();
  }, []);

  const fetchWhatsAppConfig = async () => {
    try {
      const response = await api.get('/admin/whatsapp-config');
      setWhatsappConfig(response.data);
    } catch (error) {
      console.error('Erro ao buscar configuração:', error);
    }
  };

  const handleWhatsAppSave = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      await api.put('/admin/whatsapp-config', whatsappConfig);
      setMessage({ type: 'success', content: 'Configuração do WhatsApp salva com sucesso!' });
      setTimeout(() => setMessage({ type: '', content: '' }), 3000);
    } catch (error) {
      setMessage({ type: 'error', content: 'Erro ao salvar configuração.' });
      console.error('Erro:', error);
    } finally {
      setLoading(false);
    }
  };

  const testWhatsAppConnection = async () => {
    setLoading(true);
    try {
      const response = await api.post('/admin/test-whatsapp');
      if (response.data.success) {
        setMessage({ type: 'success', content: 'Conexão com WhatsApp testada com sucesso!' });
      } else {
        setMessage({ type: 'error', content: 'Falha ao testar conexão com WhatsApp.' });
      }
    } catch (error) {
      setMessage({ type: 'error', content: 'Erro ao testar conexão.' });
      console.error('Erro:', error);
    } finally {
      setLoading(false);
      setTimeout(() => setMessage({ type: '', content: '' }), 3000);
    }
  };

  if (user.role !== 'admin') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Card className="p-8 text-center">
          <h2 className="text-2xl font-bold text-red-600 mb-4">Acesso Negado</h2>
          <p className="text-gray-600 mb-4">Apenas administradores podem acessar as configurações do sistema.</p>
          <Button onClick={onBack}>Voltar ao Dashboard</Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6" data-testid="settings-panel">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Configurações do Sistema</h1>
            <p className="text-gray-600">Configurações técnicas e integrações</p>
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
          }`} data-testid="settings-message">
            {message.content}
          </div>
        )}

        <Tabs defaultValue="whatsapp" className="space-y-6">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="whatsapp" data-testid="whatsapp-config-tab">Integração WhatsApp</TabsTrigger>
            <TabsTrigger value="system" data-testid="system-config-tab">Sistema</TabsTrigger>
          </TabsList>

          <TabsContent value="whatsapp">
            <Card className="p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-xl font-semibold">Configuração da API WhatsApp Business</h2>
                  <p className="text-gray-600">Configure as credenciais da WhatsApp Business API para integração em produção</p>
                </div>
                <Button onClick={testWhatsAppConnection} disabled={loading} data-testid="test-whatsapp-btn">
                  🧪 Testar Conexão
                </Button>
              </div>

              <form onSubmit={handleWhatsAppSave} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="access_token">Access Token *</Label>
                    <Input
                      id="access_token"
                      type="password"
                      value={whatsappConfig.access_token}
                      onChange={(e) => setWhatsappConfig({...whatsappConfig, access_token: e.target.value})}
                      placeholder="Digite o Access Token"
                      data-testid="whatsapp-access-token"
                    />
                    <p className="text-xs text-gray-500">Token de acesso permanente do Meta for Developers</p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="phone_number_id">Phone Number ID *</Label>
                    <Input
                      id="phone_number_id"
                      value={whatsappConfig.phone_number_id}
                      onChange={(e) => setWhatsappConfig({...whatsappConfig, phone_number_id: e.target.value})}
                      placeholder="Digite o Phone Number ID"
                      data-testid="whatsapp-phone-id"
                    />
                    <p className="text-xs text-gray-500">ID do número de telefone configurado no WhatsApp Business</p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="business_account_id">Business Account ID</Label>
                    <Input
                      id="business_account_id"
                      value={whatsappConfig.business_account_id}
                      onChange={(e) => setWhatsappConfig({...whatsappConfig, business_account_id: e.target.value})}
                      placeholder="Digite o Business Account ID"
                      data-testid="whatsapp-business-id"
                    />
                    <p className="text-xs text-gray-500">ID da conta comercial (opcional)</p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="webhook_verify_token">Webhook Verify Token</Label>
                    <Input
                      id="webhook_verify_token"
                      value={whatsappConfig.webhook_verify_token}
                      onChange={(e) => setWhatsappConfig({...whatsappConfig, webhook_verify_token: e.target.value})}
                      placeholder="Digite o Webhook Verify Token"
                      data-testid="whatsapp-webhook-token"
                    />
                    <p className="text-xs text-gray-500">Token para verificação do webhook (opcional)</p>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="webhook_url">Webhook URL</Label>
                  <Input
                    id="webhook_url"
                    value={whatsappConfig.webhook_url || `${window.location.origin}/api/whatsapp/webhook`}
                    onChange={(e) => setWhatsappConfig({...whatsappConfig, webhook_url: e.target.value})}
                    placeholder="https://sua-app.com/api/whatsapp/webhook"
                    data-testid="whatsapp-webhook-url"
                    className="bg-gray-50"
                    readOnly
                  />
                  <p className="text-xs text-gray-500">URL do webhook (configurada automaticamente)</p>
                </div>

                <div className="pt-4 border-t">
                  <Button type="submit" disabled={loading} className="bg-green-500 hover:bg-green-600" data-testid="save-whatsapp-config">
                    {loading ? 'Salvando...' : 'Salvar Configuração'}
                  </Button>
                </div>
              </form>

              <div className="mt-8 p-4 bg-blue-50 rounded-lg">
                <h3 className="font-semibold text-blue-900 mb-2">📋 Passo a passo para configuração:</h3>
                <ol className="text-sm text-blue-800 space-y-2 ml-4 list-decimal">
                  <li>
                    Acesse <a href="https://developers.facebook.com/" target="_blank" rel="noopener noreferrer" className="underline font-medium">Meta for Developers</a>
                  </li>
                  <li>Crie um App Business e adicione o produto "WhatsApp Business Platform"</li>
                  <li>Configure um número de telefone de teste ou produção</li>
                  <li>Gere um Access Token permanente (não temporário)</li>
                  <li>Configure o Webhook URL: <code className="bg-white px-2 py-1 rounded font-mono text-xs">{window.location.origin}/api/whatsapp/webhook</code></li>
                  <li>Ative os eventos: messages, message_deliveries, message_reads</li>
                  <li>Cole as credenciais nos campos acima e teste a conexão</li>
                </ol>
                
                <div className="mt-4 p-3 bg-white rounded border border-blue-200">
                  <p className="text-xs text-blue-700">
                    <strong>💡 Dica:</strong> Para ambiente de produção, solicite a verificação do seu App Business no Meta for Developers para remover as limitações de teste.
                  </p>
                </div>
              </div>
            </Card>
          </TabsContent>

          <TabsContent value="system">
            <div className="space-y-6">
              <Card className="p-6">
                <h2 className="text-xl font-semibold mb-4">Informações do Sistema</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  <div className="space-y-2">
                    <Label className="text-sm font-medium text-gray-600">Versão do Sistema</Label>
                    <p className="text-lg font-semibold">CRM WhatsApp v2.0.0</p>
                    <p className="text-xs text-gray-500">Última atualização: {new Date().toLocaleDateString('pt-BR')}</p>
                  </div>
                  
                  <div className="space-y-2">
                    <Label className="text-sm font-medium text-gray-600">Banco de Dados</Label>
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                      <span className="text-lg font-semibold">MongoDB</span>
                    </div>
                    <p className="text-xs text-gray-500">Status: Conectado</p>
                  </div>
                  
                  <div className="space-y-2">
                    <Label className="text-sm font-medium text-gray-600">API Backend</Label>
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                      <span className="text-lg font-semibold">FastAPI</span>
                    </div>
                    <p className="text-xs text-gray-500">Status: Online</p>
                  </div>
                  
                  <div className="space-y-2">
                    <Label className="text-sm font-medium text-gray-600">Frontend</Label>
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                      <span className="text-lg font-semibold">React</span>
                    </div>
                    <p className="text-xs text-gray-500">Status: Ativo</p>
                  </div>
                  
                  <div className="space-y-2">
                    <Label className="text-sm font-medium text-gray-600">Integração WhatsApp</Label>
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                      <span className="text-lg font-semibold">Mock Mode</span>
                    </div>
                    <p className="text-xs text-gray-500">Configure credenciais para ativar</p>
                  </div>
                  
                  <div className="space-y-2">
                    <Label className="text-sm font-medium text-gray-600">Ambiente</Label>
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                      <span className="text-lg font-semibold">Desenvolvimento</span>
                    </div>
                    <p className="text-xs text-gray-500">Emergent Cloud</p>
                  </div>
                </div>
              </Card>

              <Card className="p-6">
                <h2 className="text-xl font-semibold mb-4">Configurações de Segurança</h2>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded">
                    <div>
                      <h4 className="font-medium">Autenticação JWT</h4>
                      <p className="text-sm text-gray-600">Tokens com expiração automática</p>
                    </div>
                    <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                  </div>
                  
                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded">
                    <div>
                      <h4 className="font-medium">Hash de Senhas</h4>
                      <p className="text-sm text-gray-600">SHA-256 (desenvolver para bcrypt em produção)</p>
                    </div>
                    <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                  </div>
                  
                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded">
                    <div>
                      <h4 className="font-medium">CORS Protection</h4>
                      <p className="text-sm text-gray-600">Controle de origem de requisições</p>
                    </div>
                    <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                  </div>
                </div>
              </Card>

              <Card className="p-6">
                <h2 className="text-xl font-semibold mb-4">Recursos do Sistema</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-3">
                    <h4 className="font-medium text-gray-900">Funcionalidades Ativas</h4>
                    <ul className="space-y-2 text-sm">
                      <li className="flex items-center space-x-2">
                        <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                        <span>Sistema de autenticação</span>
                      </li>
                      <li className="flex items-center space-x-2">
                        <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                        <span>Gerenciamento de conversas</span>
                      </li>
                      <li className="flex items-center space-x-2">
                        <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                        <span>Controle de status de agentes</span>
                      </li>
                      <li className="flex items-center space-x-2">
                        <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                        <span>Métricas de performance</span>
                      </li>
                      <li className="flex items-center space-x-2">
                        <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                        <span>Histórico de atendimentos</span>
                      </li>
                    </ul>
                  </div>
                  
                  <div className="space-y-3">
                    <h4 className="font-medium text-gray-900">Próximas Funcionalidades</h4>
                    <ul className="space-y-2 text-sm">
                      <li className="flex items-center space-x-2">
                        <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                        <span>Integração WhatsApp real</span>
                      </li>
                      <li className="flex items-center space-x-2">
                        <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                        <span>Notificações push</span>
                      </li>
                      <li className="flex items-center space-x-2">
                        <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                        <span>Relatórios avançados</span>
                      </li>
                      <li className="flex items-center space-x-2">
                        <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                        <span>Bot com IA integrada</span>
                      </li>
                    </ul>
                  </div>
                </div>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default Settings;