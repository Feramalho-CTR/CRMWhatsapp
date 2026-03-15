import React, { useState } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { api } from '../App';
import { auth } from '../firebaseConfig';
import { signInWithEmailAndPassword } from 'firebase/auth';

const LoginPage = ({ onLogin }) => {
  const [formData, setFormData] = useState({
    username: '', // usado como email
    password: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // 1. Autentica no Firebase
      const userCredential = await signInWithEmailAndPassword(auth, formData.username, formData.password);
      const idToken = await userCredential.user.getIdToken();
      
      // 2. Com o token do Firebase, buscamos os dados do perfil (role, etc) no nosso backend
      // Precisamos enviar o token manualmente aqui porque o Interceptor do App.js 
      // pode não ter pegado do localStorage ainda.
      const response = await api.get('/auth/me', {
        headers: { Authorization: `Bearer ${idToken}` }
      });
      
      const user = response.data;
      onLogin(idToken, user);
    } catch (error) {
      console.error('Login error:', error);
      let errorMessage = 'Erro ao fazer login. Verifique suas credenciais.';
      
      if (error.code === 'auth/user-not-found' || error.code === 'auth/wrong-password') {
        errorMessage = 'Email ou senha incorretos.';
      } else if (error.code === 'auth/invalid-email') {
        errorMessage = 'Formato de email inválido.';
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-green-50 to-green-100 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-green-500 rounded-full mb-4">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">CRM WhatsApp</h1>
          <p className="text-gray-600">Faça login para acessar o painel</p>
        </div>

        <Card className="p-8 shadow-lg border-0 bg-white/80 backdrop-blur-sm">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="username" className="text-sm font-medium text-gray-700">
                Email
              </Label>
              <Input
                id="username"
                name="username"
                type="email"
                value={formData.username}
                onChange={handleChange}
                required
                className="h-11"
                placeholder="seu@email.com"
                data-testid="login-username-input"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium text-gray-700">
                Senha
              </Label>
              <Input
                id="password"
                name="password"
                type="password"
                value={formData.password}
                onChange={handleChange}
                required
                className="h-11"
                placeholder="Digite sua senha"
                data-testid="login-password-input"
              />
            </div>

            {error && (
              <div className="p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg" data-testid="login-error-message">
                {error}
              </div>
            )}

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-11 bg-green-500 hover:bg-green-600 text-white font-medium"
              data-testid="login-submit-button"
            >
              {loading ? (
                <div className="flex items-center justify-center">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Entrando...
                </div>
              ) : (
                'Entrar'
              )}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
};

export default LoginPage;