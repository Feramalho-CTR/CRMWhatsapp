import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from './ui/dropdown-menu';
import { api } from '../App';

const AgentStatusControl = ({ user }) => {
  const [status, setStatus] = useState('offline');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchMyStatus();
  }, []);

  const fetchMyStatus = async () => {
    try {
      const response = await api.get('/agent/my-status');
      setStatus(response.data.status);
    } catch (error) {
      console.error('Erro ao buscar status:', error);
    }
  };

  const updateStatus = async (newStatus) => {
    setLoading(true);
    try {
      await api.put('/agent/status', {
        agent_id: user.id,
        status: newStatus
      });
      setStatus(newStatus);
    } catch (error) {
      console.error('Erro ao atualizar status:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'online':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'busy':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'paused':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'offline':
        return 'bg-gray-100 text-gray-800 border-gray-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'online':
        return '🟢 Disponível';
      case 'busy':
        return '🔵 Em atendimento';
      case 'paused':
        return '🟡 Em pausa';
      case 'offline':
        return '⚫ Offline';
      default:
        return status;
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'online':
        return '🟢';
      case 'busy':
        return '🔵';
      case 'paused':
        return '🟡';
      case 'offline':
        return '⚫';
      default:
        return '⚫';
    }
  };

  return (
    <div className="flex items-center space-x-3" data-testid="agent-status-control">
      <Badge className={`${getStatusColor(status)} px-3 py-1 text-sm border`}>
        {getStatusText(status)}
      </Badge>
      
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button 
            variant="outline" 
            size="sm" 
            disabled={loading}
            className="text-xs"
            data-testid="change-status-btn"
          >
            {loading ? '...' : 'Alterar Status'}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem 
            onClick={() => updateStatus('online')}
            disabled={status === 'online'}
            data-testid="status-online"
          >
            🟢 Disponível (Online)
          </DropdownMenuItem>
          <DropdownMenuItem 
            onClick={() => updateStatus('paused')}
            disabled={status === 'paused'}
            data-testid="status-paused"
          >
            🟡 Em pausa (Almoço/Intervalo)
          </DropdownMenuItem>
          <DropdownMenuItem 
            onClick={() => updateStatus('offline')}
            disabled={status === 'offline'}
            data-testid="status-offline"
          >
            ⚫ Offline (Fim do expediente)
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
};

export default AgentStatusControl;