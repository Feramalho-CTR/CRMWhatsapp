import React, { useState } from 'react';
import ContactCard from './ContactCard';
import { Button } from './ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "./ui/dialog";
import { ScrollArea } from "./ui/scroll-area";
import { Badge } from './ui/badge';

const ContactsList = ({ contacts }) => {
  const [isOpen, setIsOpen] = useState(false);

  if (!Array.isArray(contacts) || contacts.length === 0) {
    return null;
  }

  // Caso 1: Apenas 1 contato - renderiza direto
  if (contacts.length === 1) {
    return <ContactCard contact={contacts[0]} />;
  }

  // Caso 2: Múltiplos contatos - renderiza resumo e gatilho para Modal
  return (
    <div className="mt-2 mb-2 w-full max-w-sm">
      <div className="bg-white rounded-lg border border-gray-100 shadow-sm p-4 flex flex-col items-center justify-center space-y-3">
        <div className="flex items-center space-x-2 text-green-600">
          <div className="p-2 bg-green-50 rounded-full">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          </div>
          <span className="font-bold text-sm">Lista de Contatos</span>
        </div>
        
        <p className="text-xs text-gray-500 text-center">
          Você recebeu um conjunto de <span className="font-bold text-gray-800">{contacts.length} contatos</span>.
        </p>

        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <Button variant="outline" className="w-full text-xs font-bold border-green-200 text-green-700 hover:bg-green-50 hover:text-green-800 transition-all">
              VER TODOS OS CONTATOS
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[425px] max-h-[85vh] flex flex-col p-0 overflow-hidden border-none shadow-2xl">
            <DialogHeader className="p-6 bg-gradient-to-r from-green-500 to-green-600 text-white">
              <DialogTitle className="flex items-center justify-between">
                <span>Contatos Recebidos</span>
                <Badge className="bg-white/20 text-white border-none text-[10px] uppercase font-bold px-2 py-0.5">
                  {contacts.length} Itens
                </Badge>
              </DialogTitle>
            </DialogHeader>
            <ScrollArea className="flex-1 p-6 bg-gray-50">
              <div className="space-y-4 pb-4">
                {contacts.map((contact, index) => (
                  <ContactCard key={index} contact={contact} />
                ))}
              </div>
            </ScrollArea>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
};

export default ContactsList;
