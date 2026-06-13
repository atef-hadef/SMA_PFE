'use client';

import React, { useState } from 'react';
import { Bell, Settings, TrendingUp, AlertCircle, CheckCircle, Clock, Users, BarChart3, Activity, ChevronRight, Search, Filter, Eye, FileText, Check, X, Calendar, Zap, Bot, Lock } from 'lucide-react';

export function DashboardPreview() {
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [selectedLead, setSelectedLead] = useState(null);
  const [selectedRequest, setSelectedRequest] = useState(null);

  // Sidebar navigation
  const navItems = [
    { id: 'dashboard', label: 'Tableau de bord', icon: BarChart3 },
    { id: 'crm', label: 'CRM intelligent', icon: TrendingUp },
    { id: 'client-details', label: 'Détails client', icon: Users },
    { id: 'leave', label: 'Demandes de congé', icon: Calendar },
    { id: 'approvals', label: 'Validations manager', icon: Check },
    { id: 'workflows', label: 'Automatisations', icon: Zap },
    { id: 'agents', label: 'Agents IA', icon: Bot },
    { id: 'users', label: 'Utilisateurs', icon: Users },
    { id: 'permissions', label: 'Rôles & permissions', icon: Lock },
  ];

  // Mock data for all pages
  const kpis = [
    { label: 'Leads Chauds', value: '12', trend: '+3', color: 'from-emerald-500 to-emerald-600' },
    { label: 'Brouillons CRM', value: '8', trend: '-2', color: 'from-blue-500 to-blue-600' },
    { label: 'Demandes de Congé', value: '5', trend: '+1', color: 'from-purple-500 to-purple-600' },
    { label: 'Automatisations OK', value: '24', trend: '+4', color: 'from-orange-500 to-orange-600' },
  ];

  const crmLeads = [
    { id: 1, name: 'Acme Corp', company: 'Acme', email: 'contact@acme.com', phone: '+33123456789', status: 'Lead', score: 87, priority: 'Élevée', value: '45k€', interest: 'SaaS', owner: 'Marie', source: 'LinkedIn', lastContact: '2 jours', nextAction: 'Appel' },
    { id: 2, name: 'TechFlow Inc', company: 'TechFlow', email: 'sales@techflow.com', phone: '+33987654321', status: 'Prospect', score: 75, priority: 'Moyenne', value: '32k€', interest: 'Services', owner: 'Jean', source: 'Email', lastContact: '1 jour', nextAction: 'Réunion' },
    { id: 3, name: 'Global Solutions', company: 'Global', email: 'info@global.com', phone: '+33111222333', status: 'Client', score: 92, priority: 'Élevée', value: '78k€', interest: 'Support', owner: 'Sophie', source: 'Référence', lastContact: 'Aujourd\'hui', nextAction: 'Livraison' },
  ];

  const users = [
    { id: 1, name: 'Marie Dupont', email: 'marie@flowpilot.com', role: 'Manager', dept: 'Ventes', status: 'Actif', lastActivity: '2 min' },
    { id: 2, name: 'Jean Martin', email: 'jean@flowpilot.com', role: 'Sales', dept: 'Ventes', status: 'Actif', lastActivity: '1 heure' },
    { id: 3, name: 'Sophie Bernard', email: 'sophie@flowpilot.com', role: 'Admin', dept: 'IT', status: 'Actif', lastActivity: '30 min' },
  ];

  const roles = [
    { name: 'Admin', perms: { crm: ['Lire', 'Créer', 'Modifier', 'Supprimer'], leave: ['Lire', 'Modifier'], workflows: ['Lire', 'Exécuter'], agents: ['Lire', 'Modifier'], admin: ['Lire', 'Modifier'] } },
    { name: 'Manager', perms: { crm: ['Lire', 'Créer'], leave: ['Lire', 'Valider'], workflows: ['Lire'], agents: ['Lire'], admin: [] } },
    { name: 'Sales', perms: { crm: ['Lire', 'Créer', 'Modifier'], leave: ['Lire', 'Créer'], workflows: ['Lire'], agents: [], admin: [] } },
  ];

  const agents = [
    { name: 'Agent Analyse CRM', role: 'Scoring & Qualification', process: 'CRM', status: 'Actif', lastRun: '2 min', success: 47, impact: 'Leads qualifiés' },
    { name: 'Agent Communication CRM', role: 'Rédaction', process: 'CRM', status: 'Actif', lastRun: '5 min', success: 12, impact: 'Brouillons créés' },
    { name: 'Agent Routage Commercial', role: 'Distribution', process: 'CRM', status: 'En attente', lastRun: '15 min', success: 8, impact: 'Assignations' },
    { name: 'Agent Analyse Congé', role: 'Validation', process: 'Congés', status: 'Actif', lastRun: '1 min', success: 5, impact: 'Demandes analysées' },
  ];

  const leaveRequests = [
    { id: 1, employee: 'Marie Dupont', type: 'Congés annuels', startDate: '15 Juil 2024', endDate: '29 Juil 2024', days: 10, reason: 'Vacances', status: 'En attente', step: 2 },
    { id: 2, employee: 'Jean Martin', type: 'RTT', startDate: '10 Juil 2024', endDate: '10 Juil 2024', days: 1, reason: 'Personnel', status: 'Approuvée', step: 4 },
  ];

  // Page components
  const PageDashboard = () => (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Métriques Clés</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {kpis.map((kpi, i) => (
            <div key={i} className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6 hover:border-slate-600 transition">
              <p className="text-slate-400 text-sm mb-2">{kpi.label}</p>
              <div className="flex items-end justify-between">
                <div className="text-4xl font-bold text-white">{kpi.value}</div>
                <div className={`bg-gradient-to-br ${kpi.color} text-white px-3 py-1 rounded-lg text-sm font-medium flex items-center gap-1`}>
                  <TrendingUp size={14} />
                  {kpi.trend}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Santé des Automatisations</h3>
          <div className="space-y-3">
            {[{ name: 'CRM', percent: 96 }, { name: 'Congés', percent: 92 }, { name: 'Gmail', percent: 88 }].map((item, i) => (
              <div key={i}>
                <div className="flex justify-between mb-1 text-sm">
                  <span className="text-slate-300">{item.name}</span>
                  <span className="text-emerald-400">{item.percent}%</span>
                </div>
                <div className="w-full bg-slate-700 rounded-full h-2 overflow-hidden">
                  <div className="bg-gradient-to-r from-emerald-500 to-emerald-400 h-full" style={{ width: `${item.percent}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Agents IA Actifs</h3>
          <div className="space-y-2">
            {[{ name: 'Analyse CRM', status: 'actif' }, { name: 'Communication', status: 'actif' }, { name: 'Routage', status: 'inactif' }, { name: 'Congés', status: 'actif' }].map((agent, i) => (
              <div key={i} className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${agent.status === 'actif' ? 'bg-green-500' : 'bg-slate-500'}`} />
                <span className="text-sm text-slate-300">{agent.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Activité Récente</h3>
        <div className="space-y-3">
          {[
            { action: 'Nouveau Lead', desc: 'Acme Corp', time: '2 min' },
            { action: 'Brouillon Créé', desc: 'TechFlow Inc', time: '15 min' },
            { action: 'Workflow Exécuté', desc: 'Synchronisation Odoo', time: '1 heure' },
          ].map((item, i) => (
            <div key={i} className="flex justify-between text-sm border-b border-slate-700 pb-3 last:border-0">
              <span className="text-white">{item.action}</span>
              <span className="text-slate-400">{item.time}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const PageCRM = () => (
    <div className="space-y-6">
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search size={18} className="absolute left-3 top-3 text-slate-400" />
          <input type="text" placeholder="Rechercher..." className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-10 pr-4 py-2 text-white placeholder-slate-500" />
        </div>
        <button className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-white flex items-center gap-2 hover:bg-slate-700">
          <Filter size={18} /> Filtres
        </button>
      </div>

      <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="px-6 py-3 text-left text-sm font-medium text-slate-400">Nom</th>
                <th className="px-6 py-3 text-left text-sm font-medium text-slate-400">Statut</th>
                <th className="px-6 py-3 text-left text-sm font-medium text-slate-400">Score IA</th>
                <th className="px-6 py-3 text-left text-sm font-medium text-slate-400">Priorité</th>
                <th className="px-6 py-3 text-left text-sm font-medium text-slate-400">Valeur</th>
                <th className="px-6 py-3 text-left text-sm font-medium text-slate-400">Actions</th>
              </tr>
            </thead>
            <tbody>
              {crmLeads.map((lead) => (
                <tr key={lead.id} className="border-b border-slate-700 hover:bg-slate-800/50">
                  <td className="px-6 py-4 text-sm text-white">{lead.name}</td>
                  <td className="px-6 py-4 text-sm"><span className="bg-blue-500/20 text-blue-300 px-2 py-1 rounded text-xs">{lead.status}</span></td>
                  <td className="px-6 py-4 text-sm text-emerald-400">{lead.score}</td>
                  <td className="px-6 py-4 text-sm"><span className={`px-2 py-1 rounded text-xs ${lead.priority === 'Élevée' ? 'bg-red-500/20 text-red-300' : 'bg-yellow-500/20 text-yellow-300'}`}>{lead.priority}</span></td>
                  <td className="px-6 py-4 text-sm text-slate-300">{lead.value}</td>
                  <td className="px-6 py-4 text-sm flex gap-2">
                    <button onClick={() => { setSelectedLead(lead); setCurrentPage('client-details'); }} className="text-blue-400 hover:text-blue-300 flex items-center gap-1">
                      <Eye size={16} /> Voir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );

  const PageClientDetails = () => (
    <div className="space-y-6">
      {selectedLead && (
        <>
          <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6">
            <div className="flex justify-between items-start mb-6">
              <div>
                <h2 className="text-2xl font-bold text-white">{selectedLead.name}</h2>
                <p className="text-slate-400">{selectedLead.company}</p>
              </div>
              <div className="flex gap-2">
                <span className="bg-blue-500/20 text-blue-300 px-3 py-1 rounded-lg text-sm">{selectedLead.status}</span>
                <span className="bg-red-500/20 text-red-300 px-3 py-1 rounded-lg text-sm">{selectedLead.priority}</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div>
                <h3 className="text-sm font-medium text-slate-400 mb-2">Coordonnées</h3>
                <div className="space-y-2 text-sm text-slate-300">
                  <p>Email: {selectedLead.email}</p>
                  <p>Téléphone: {selectedLead.phone}</p>
                  <p>Propriétaire: {selectedLead.owner}</p>
                </div>
              </div>
              <div>
                <h3 className="text-sm font-medium text-slate-400 mb-2">Informations</h3>
                <div className="space-y-2 text-sm text-slate-300">
                  <p>Score IA: <span className="text-emerald-400 font-bold">{selectedLead.score}</span></p>
                  <p>Valeur estimée: {selectedLead.value}</p>
                  <p>Intérêt: {selectedLead.interest}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Parcours Client</h3>
            <div className="flex items-center gap-2">
              {['Lead', 'Prospect', 'Client', 'Client actif'].map((stage, i) => (
                <React.Fragment key={i}>
                  <div className={`flex items-center justify-center w-10 h-10 rounded-full ${selectedLead.status === stage ? 'bg-emerald-500 text-white' : 'bg-slate-700 text-slate-400'}`}>
                    {i + 1}
                  </div>
                  {i < 3 && <div className="flex-1 h-1 bg-slate-700" />}
                </React.Fragment>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6">
              <h3 className="text-lg font-semibold text-white mb-4">Derniers Contacts</h3>
              <div className="space-y-2 text-sm text-slate-300">
                <p>Dernier contact: {selectedLead.lastContact}</p>
                <p>Prochaine action: {selectedLead.nextAction}</p>
              </div>
            </div>
            <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6">
              <h3 className="text-lg font-semibold text-white mb-4">Insight IA</h3>
              <p className="text-sm text-slate-300">Score élevé indiquant une forte probabilité de conversion dans les 30 jours.</p>
            </div>
          </div>
        </>
      )}
    </div>
  );

  const PageLeave = () => (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Nouvelle Demande de Congé</h2>
        <div className="grid grid-cols-2 gap-4">
          <input type="text" placeholder="Type de congé" className="bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-500" />
          <input type="date" className="bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 text-white" />
          <input type="date" className="bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 text-white" />
          <textarea placeholder="Motif" className="bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-500 col-span-2" rows="3" />
          <button className="col-span-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg px-4 py-2 font-medium">Soumettre</button>
        </div>
      </div>

      <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Processus de Demande</h3>
        <div className="space-y-3">
          {[
            { step: 1, title: 'Demande soumise', status: 'done' },
            { step: 2, title: 'Analyse automatique IA', status: 'done' },
            { step: 3, title: 'Validation manager', status: 'active' },
            { step: 4, title: 'Synchronisation Odoo', status: 'pending' },
            { step: 5, title: 'Décision finale', status: 'pending' },
          ].map((item) => (
            <div key={item.step} className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${item.status === 'done' ? 'bg-emerald-500 text-white' : item.status === 'active' ? 'bg-blue-500 text-white' : 'bg-slate-700 text-slate-400'}`}>
                {item.status === 'done' ? '✓' : item.step}
              </div>
              <span className="text-slate-300">{item.title}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Dernière Demande</h3>
        {leaveRequests[0] && (
          <div className="space-y-3">
            <div className="flex justify-between"><span className="text-slate-400">Employé:</span> <span className="text-white">{leaveRequests[0].employee}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">Type:</span> <span className="text-white">{leaveRequests[0].type}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">Période:</span> <span className="text-white">{leaveRequests[0].startDate} au {leaveRequests[0].endDate}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">Statut:</span> <span className="bg-yellow-500/20 text-yellow-300 px-2 py-1 rounded text-xs">{leaveRequests[0].status}</span></div>
          </div>
        )}
      </div>
    </div>
  );

  const PageApprovals = () => (
    <div className="grid grid-cols-3 gap-6">
      <div className="col-span-1">
        <h2 className="text-lg font-semibold text-white mb-4">Demandes en Attente ({leaveRequests.length})</h2>
        <div className="space-y-2">
          {leaveRequests.map((req) => (
            <button
              key={req.id}
              onClick={() => setSelectedRequest(req)}
              className={`w-full text-left p-3 rounded-lg border transition ${
                selectedRequest?.id === req.id
                  ? 'bg-emerald-500/20 border-emerald-500'
                  : 'bg-slate-800 border-slate-700 hover:border-slate-600'
              }`}
            >
              <p className="text-white font-medium text-sm">{req.employee}</p>
              <p className="text-slate-400 text-xs">{req.type}</p>
            </button>
          ))}
        </div>
      </div>

      <div className="col-span-2">
        {selectedRequest && (
          <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Détails de la Demande</h3>
            <div className="space-y-4 mb-6">
              <div className="flex justify-between"><span className="text-slate-400">Employé:</span> <span className="text-white font-medium">{selectedRequest.employee}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Type de congé:</span> <span className="text-white">{selectedRequest.type}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Période:</span> <span className="text-white">{selectedRequest.startDate} - {selectedRequest.endDate}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Nombre de jours:</span> <span className="text-white font-bold">{selectedRequest.days}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Motif:</span> <span className="text-white">{selectedRequest.reason}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Recommandation IA:</span> <span className="text-emerald-400">Approuver</span></div>
            </div>
            <textarea placeholder="Commentaire manager..." className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-500 mb-4" rows="3" />
            <div className="flex gap-3">
              <button className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg px-4 py-2 font-medium flex items-center justify-center gap-2">
                <Check size={18} /> Approuver
              </button>
              <button className="flex-1 bg-red-600 hover:bg-red-700 text-white rounded-lg px-4 py-2 font-medium flex items-center justify-center gap-2">
                <X size={18} /> Rejeter
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );

  const PageWorkflows = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {[
          { name: 'CRM', step: 'Analyse Lead', status: 'Réussi', count: 24 },
          { name: 'Congés', step: 'Validation Manager', status: 'En attente', count: 3 },
          { name: 'Gmail', step: 'Envoi Email', status: 'Réussi', count: 18 },
          { name: 'Odoo', step: 'Synchronisation', status: 'Échec', count: 1 },
        ].map((wf, i) => (
          <div key={i} className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-semibold text-white">{wf.name}</h3>
                <p className="text-slate-400 text-sm">{wf.step}</p>
              </div>
              <span className={`px-3 py-1 rounded-lg text-sm font-medium ${wf.status === 'Réussi' ? 'bg-emerald-500/20 text-emerald-300' : wf.status === 'En attente' ? 'bg-yellow-500/20 text-yellow-300' : 'bg-red-500/20 text-red-300'}`}>
                {wf.status}
              </span>
            </div>
            <p className="text-2xl font-bold text-white mb-4">{wf.count} exécutions</p>
            {wf.status === 'Échec' && <button className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg px-3 py-2 text-sm font-medium">Réessayer</button>}
          </div>
        ))}
      </div>

      <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Historique d'Exécution</h3>
        <div className="space-y-2">
          {[
            { workflow: 'CRM Analysis', time: '2 min', result: 'OK', count: '5 leads' },
            { workflow: 'Leave Processing', time: '5 min', result: 'OK', count: '1 demande' },
            { workflow: 'Odoo Sync', time: '15 min', result: 'FAIL', count: 'Réseau' },
          ].map((item, i) => (
            <div key={i} className="flex justify-between items-center p-3 bg-slate-900/50 rounded-lg border border-slate-700">
              <div>
                <p className="text-white text-sm">{item.workflow}</p>
                <p className="text-slate-400 text-xs">{item.count}</p>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-slate-400 text-sm">{item.time}</span>
                <span className={`px-2 py-1 rounded text-xs font-medium ${item.result === 'OK' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-red-500/20 text-red-300'}`}>{item.result}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const PageAgents = () => (
    <div className="space-y-6">
      {agents.map((agent, i) => (
        <div key={i} className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="text-lg font-semibold text-white">{agent.name}</h3>
              <p className="text-slate-400 text-sm">{agent.role}</p>
            </div>
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${agent.status === 'Actif' ? 'bg-green-500' : 'bg-yellow-500'}`} />
              <span className="text-slate-300 text-sm">{agent.status}</span>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div><p className="text-slate-400 text-xs">Processus</p> <p className="text-white font-medium">{agent.process}</p></div>
            <div><p className="text-slate-400 text-xs">Dernière exécution</p> <p className="text-white font-medium">{agent.lastRun}</p></div>
            <div><p className="text-slate-400 text-xs">Impact métier</p> <p className="text-white font-medium">{agent.impact}</p></div>
          </div>
          <button className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg px-3 py-2 text-sm font-medium">Exécuter</button>
        </div>
      ))}
    </div>
  );

  const PageUsers = () => (
    <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-700">
              <th className="px-6 py-3 text-left text-sm font-medium text-slate-400">Nom</th>
              <th className="px-6 py-3 text-left text-sm font-medium text-slate-400">Email</th>
              <th className="px-6 py-3 text-left text-sm font-medium text-slate-400">Rôle</th>
              <th className="px-6 py-3 text-left text-sm font-medium text-slate-400">Département</th>
              <th className="px-6 py-3 text-left text-sm font-medium text-slate-400">Statut</th>
              <th className="px-6 py-3 text-left text-sm font-medium text-slate-400">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id} className="border-b border-slate-700 hover:bg-slate-800/50">
                <td className="px-6 py-4 text-sm text-white">{user.name}</td>
                <td className="px-6 py-4 text-sm text-slate-300">{user.email}</td>
                <td className="px-6 py-4 text-sm text-slate-300">{user.role}</td>
                <td className="px-6 py-4 text-sm text-slate-300">{user.dept}</td>
                <td className="px-6 py-4 text-sm"><span className="bg-emerald-500/20 text-emerald-300 px-2 py-1 rounded text-xs">{user.status}</span></td>
                <td className="px-6 py-4 text-sm flex gap-2">
                  <button className="text-blue-400 hover:text-blue-300">Éditer</button>
                  <button className="text-amber-400 hover:text-amber-300">Désactiver</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  const PagePermissions = () => (
    <div className="space-y-6">
      {roles.map((role, i) => (
        <div key={i} className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4">{role.name}</h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {Object.entries(role.perms).map(([category, perms]) => (
              <div key={category}>
                <p className="text-slate-400 text-sm font-medium mb-2 capitalize">{category}</p>
                <div className="space-y-2">
                  {perms.length === 0 ? (
                    <p className="text-slate-500 text-xs">Aucune permission</p>
                  ) : (
                    perms.map((perm) => (
                      <label key={perm} className="flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" defaultChecked className="w-4 h-4 rounded bg-slate-700 border-slate-600" />
                        <span className="text-slate-300 text-sm">{perm}</span>
                      </label>
                    ))
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
      <button className="w-full bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg px-4 py-2 font-medium">Sauvegarder les modifications</button>
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="flex items-center justify-between px-8 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center font-bold text-white">
              FP
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">FlowPilot AI</h1>
              <p className="text-xs text-slate-400">Prototype Complet</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button className="p-2 hover:bg-slate-800 rounded-lg transition">
              <Bell size={20} className="text-slate-400" />
            </button>
            <button className="p-2 hover:bg-slate-800 rounded-lg transition">
              <Settings size={20} className="text-slate-400" />
            </button>
          </div>
        </div>
      </header>

      <div className="flex">
        <aside className="w-64 border-r border-slate-800 bg-slate-950/50 p-6 hidden md:block max-h-[calc(100vh-70px)] overflow-y-auto">
          <nav className="space-y-2">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => setCurrentPage(item.id)}
                className={`w-full flex items-center gap-3 px-4 py-2 rounded-lg transition ${
                  currentPage === item.id
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : 'text-slate-400 hover:bg-slate-800'
                }`}
              >
                <item.icon size={18} />
                <span className="text-sm">{item.label}</span>
              </button>
            ))}
          </nav>
        </aside>

        <main className="flex-1 overflow-y-auto max-h-[calc(100vh-70px)]">
          <div className="p-8">
            {currentPage === 'dashboard' && <PageDashboard />}
            {currentPage === 'crm' && <PageCRM />}
            {currentPage === 'client-details' && <PageClientDetails />}
            {currentPage === 'leave' && <PageLeave />}
            {currentPage === 'approvals' && <PageApprovals />}
            {currentPage === 'workflows' && <PageWorkflows />}
            {currentPage === 'agents' && <PageAgents />}
            {currentPage === 'users' && <PageUsers />}
            {currentPage === 'permissions' && <PagePermissions />}
          </div>
        </main>
      </div>
    </div>
  );
}
