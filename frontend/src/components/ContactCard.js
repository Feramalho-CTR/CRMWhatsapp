import React from 'react';
import { Card, CardContent } from './ui/card';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';
import { Badge } from './ui/badge';

const ContactCard = ({ contact }) => {
  // A estrutura do contato do WhatsApp é geralmente:
  // { name: { formatted_name: '...', first_name: '...' }, phones: [{ phone: '...', type: '...' }] }
  
  const displayName = contact.name?.formatted_name || contact.name?.first_name || 'Contato sem nome';
  const phones = contact.phones || [];
  const initials = displayName
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <Card className="w-full max-w-sm overflow-hidden border-none shadow-md bg-white hover:shadow-lg transition-shadow duration-200 mt-2 mb-2">
      <CardContent className="p-4">
        <div className="flex items-center space-x-4">
          <Avatar className="h-12 w-12 border-2 border-green-100">
            <AvatarFallback className="bg-gradient-to-br from-green-400 to-green-600 text-white font-bold">
              {initials}
            </AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-bold text-gray-900 truncate">
              {displayName}
            </h4>
            <div className="space-y-1 mt-1">
              {phones.map((p, idx) => (
                <div key={idx} className="flex items-center text-xs text-gray-500">
                  <span className="mr-2">📱</span>
                  <span className="truncate">{p.phone}</span>
                  {p.type && (
                    <Badge variant="outline" className="ml-2 scale-75 origin-left text-[10px] py-0 px-1 border-gray-200 text-gray-400 capitalize">
                      {p.type}
                    </Badge>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
        
        <div className="mt-4 pt-3 border-t border-gray-50 flex items-center justify-between">
          <button 
            className="text-[11px] font-bold text-green-600 hover:text-green-700 flex items-center transition-colors"
            onClick={() => window.open(`https://wa.me/${phones[0]?.phone?.replace(/\D/g, '')}`, '_blank')}
          >
            <span className="mr-1">💬</span> CONVERSAR
          </button>
          
          <Badge variant="secondary" className="bg-blue-50 text-blue-600 border-none text-[9px] font-bold py-0.5 px-2">
            CARTÃO DE CONTATO
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
};

export default ContactCard;
