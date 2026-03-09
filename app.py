import React, { useState, useMemo, useRef, useEffect } from 'react';
import { initializeApp } from 'firebase/app';
import { getAuth, signInAnonymously, signInWithCustomToken, onAuthStateChanged } from 'firebase/auth';
import { getFirestore, collection, addDoc, deleteDoc, doc, onSnapshot } from 'firebase/firestore';
import { 
  Activity, 
  Bike, 
  Waves, 
  Snowflake, 
  Footprints, 
  Dumbbell, 
  Plus, 
  Trash2, 
  BarChart3, 
  Clock, 
  MapPin,
  Download,
  Upload,
  AlertCircle,
  CheckCircle2,
  Landmark,
  FileJson,
  Cloud,
  Loader2,
  Sparkles,
  Volume2,
  Brain,
  Copy,
  TrendingUp,
  Infinity,
  Smartphone,
  ExternalLink,
  ShieldCheck
} from 'lucide-react';

// --- KONFIGURACJA FIREBASE ---
const firebaseConfig = JSON.parse(__firebase_config);
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
const appId = typeof __app_id !== 'undefined' ? __app_id : 'fitness-tracker-v1';

// --- KONFIGURACJA GEMINI API ---
const apiKey = ""; 

const ACTIVITY_TYPES = {
  running: { label: 'Bieganie', icon: Activity, bgColor: 'bg-orange-100', iconColor: 'text-orange-600', borderColor: 'border-orange-200', avgPace: 6 },
  cycling: { label: 'Rower', icon: Bike, bgColor: 'bg-blue-100', iconColor: 'text-blue-600', borderColor: 'border-blue-200', avgPace: 3 },
  swimming: { label: 'Pływanie', icon: Waves, bgColor: 'bg-cyan-100', iconColor: 'text-cyan-600', borderColor: 'border-cyan-200', avgPace: 20 },
  skiing: { label: 'Narty', icon: Snowflake, bgColor: 'bg-indigo-100', iconColor: 'text-indigo-600', borderColor: 'border-indigo-200', avgPace: 4 }, 
  walking: { label: 'Spacer', icon: Footprints, bgColor: 'bg-green-100', iconColor: 'text-green-600', borderColor: 'border-green-200', avgPace: 12 },
  sightseeing: { label: 'Zwiedzanie', icon: Landmark, bgColor: 'bg-amber-100', iconColor: 'text-amber-600', borderColor: 'border-amber-200', avgPace: 15 },
  gym: { label: 'Siłownia', icon: Dumbbell, bgColor: 'bg-purple-100', iconColor: 'text-purple-600', borderColor: 'border-purple-200', avgPace: null }
};

const pcmToWav = (pcmData, sampleRate) => {
  const buffer = new ArrayBuffer(44 + pcmData.length * 2);
  const view = new DataView(buffer);
  const writeString = (offset, string) => {
    for (let i = 0; i < string.length; i++) view.setUint8(offset + i, string.charCodeAt(i));
  };
  writeString(0, 'RIFF');
  view.setUint32(4, 36 + pcmData.length * 2, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, 'data');
  view.setUint32(40, pcmData.length * 2, true);
  for (let i = 0; i < pcmData.length; i++) view.setInt16(44 + i * 2, pcmData[i], true);
  return buffer;
};

const App = () => {
  const [user, setUser] = useState(null);
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showInstallGuide, setShowInstallGuide] = useState(false);
  const [activeTab, setActiveTab] = useState('list');
  const [statusMsg, setStatusMsg] = useState(null);
  const fileInputRef = useRef(null);
  
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [isTtsLoading, setIsTtsLoading] = useState(false);

  const [formData, setFormData] = useState({
    type: 'running',
    distance: '',
    duration: '',
    date: new Date().toISOString().split('T')[0]
  });

  useEffect(() => {
    const initAuth = async () => {
      try {
        if (typeof __initial_auth_token !== 'undefined' && __initial_auth_token) {
          await signInWithCustomToken(auth, __initial_auth_token);
        } else {
          await signInAnonymously(auth);
        }
      } catch (e) {}
    };
    initAuth();
    const unsubscribe = onAuthStateChanged(auth, (u) => {
      setUser(u);
      if (!u) setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  useEffect(() => {
    if (!user) return;
    const activitiesCol = collection(db, 'artifacts', appId, 'users', user.uid, 'activities');
    const unsubscribe = onSnapshot(activitiesCol, (snapshot) => {
      const data = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
      setActivities(data.sort((a, b) => b.timestamp - a.timestamp));
      setLoading(false);
    }, (error) => { setLoading(false); });
    return () => unsubscribe();
  }, [user]);

  const showStatus = (text, type = 'success') => {
    setStatusMsg({ text, type });
    setTimeout(() => setStatusMsg(null), 3000);
  };

  const callGeminiWithRetry = async (url, payload, retries = 5, delay = 1000) => {
    for (let i = 0; i < retries; i++) {
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (response.ok) return await response.json();
      } catch (e) {}
      await new Promise(res => setTimeout(res, delay));
      delay *= 2;
    }
    throw new Error("API error");
  };

  const generateAiAnalysis = async () => {
    if (activities.length === 0) return showStatus("Brak danych", "error");
    setIsAiLoading(true);
    const summaryText = activities.slice(0, 10).map(a => `${a.date}: ${ACTIVITY_TYPES[a.type].label}, ${a.distance}km`).join("; ");
    try {
      const result = await callGeminiWithRetry(
        `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key=${apiKey}`,
        { contents: [{ parts: [{ text: `Przeanalizuj moje treningi i daj krótką radę po polsku: ${summaryText}` }] }] }
      );
      setAiAnalysis(result.candidates?.[0]?.content?.parts?.[0]?.text);
    } catch (err) { showStatus("Błąd AI", "error"); }
    finally { setIsAiLoading(false); }
  };

  const playMotivationalSpeech = async () => {
    setIsTtsLoading(true);
    try {
      const result = await callGeminiWithRetry(
        `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts?key=${apiKey}`,
        {
          contents: [{ parts: [{ text: `Powiedz entuzjastycznie po polsku: Brawo! Masz już ${activities.length} treningów na koncie. Tak trzymaj!` }] }],
          generationConfig: {
            responseModalities: ["AUDIO"],
            speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: "Puck" } } }
          },
          model: "gemini-2.5-flash-preview-tts"
        }
      );
      const base64Audio = result.candidates[0].content.parts[0].inlineData.data;
      const bytes = new Int16Array(window.atob(base64Audio).length / 2);
      const binary = window.atob(base64Audio);
      for (let i = 0; i < binary.length; i += 2) bytes[i / 2] = (binary.charCodeAt(i + 1) << 8) | binary.charCodeAt(i);
      const audio = new Audio(URL.createObjectURL(new Blob([pcmToWav(bytes, 24000)], { type: 'audio/wav' })));
      audio.play();
    } catch (err) { showStatus("Błąd TTS", "error"); }
    finally { setIsTtsLoading(false); }
  };

  const handleAddActivity = async (e) => {
    e.preventDefault();
    if (!user || (!formData.distance && !formData.duration)) return;
    const typeConfig = ACTIVITY_TYPES[formData.type];
    let d = parseFloat(formData.distance) || 0;
    let t = parseFloat(formData.duration) || 0;
    if (!d && t && typeConfig.avgPace) d = parseFloat((t / typeConfig.avgPace).toFixed(2));
    else if (d && !t && typeConfig.avgPace) t = Math.round(d * typeConfig.avgPace);
    
    try {
      await addDoc(collection(db, 'artifacts', appId, 'users', user.uid, 'activities'), {
        type: formData.type, distance: d, duration: t, date: formData.date,
        timestamp: new Date(formData.date + "T00:00:00").getTime()
      });
      setShowAddModal(false);
      setFormData({ ...formData, distance: '', duration: '', date: new Date().toISOString().split('T')[0] });
      showStatus("Dodano!");
    } catch (e) { showStatus("Błąd", "error"); }
  };

  const deleteActivity = async (id) => {
    if (!user) return;
    try {
      await deleteDoc(doc(db, 'artifacts', appId, 'users', user.uid, 'activities', id));
      showStatus("Usunięto");
    } catch (e) { showStatus("Błąd", "error"); }
  };

  // --- ZARZĄDZANIE DANYMI (ARCHIWIZACJA) ---
  const exportData = () => {
    if (activities.length === 0) return showStatus("Brak danych", "error");
    const dataStr = JSON.stringify(activities, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `FitTracker_Backup_${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    showStatus("Plik JSON pobrany!");
  };

  const copyDataToClipboard = () => {
    const dataStr = JSON.stringify(activities);
    const el = document.createElement('textarea');
    el.value = dataStr;
    document.body.appendChild(el);
    el.select();
    document.execCommand('copy');
    document.body.removeChild(el);
    showStatus("Kod kopii w schowku!");
  };

  const importData = async (e) => {
    const file = e.target.files[0];
    if (!file || !user) return;
    const reader = new FileReader();
    reader.onload = async (event) => {
      try {
        const imported = JSON.parse(event.target.result);
        if (Array.isArray(imported)) {
          const colRef = collection(db, 'artifacts', appId, 'users', user.uid, 'activities');
          showStatus(`Importowanie ${imported.length} wpisów...`);
          for (const item of imported) {
            const { id, ...data } = item;
            await addDoc(colRef, data);
          }
          showStatus("Dane przywrócone!");
        }
      } catch (err) { showStatus("Błąd pliku", "error"); }
    };
    reader.readAsText(file);
    e.target.value = ''; 
  };

  const stats = useMemo(() => {
    const now = new Date();
    const day = now.getDay();
    const diff = now.getDate() - day + (day === 0 ? -6 : 1);
    const startOfWeek = new Date(new Date().setDate(diff)).setHours(0,0,0,0);
    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1).getTime();
    const startOfYear = new Date(now.getFullYear(), 0, 1).getTime();
    const calc = (items) => ({
      count: items.length,
      distance: items.reduce((acc, curr) => acc + curr.distance, 0).toFixed(1),
      duration: items.reduce((acc, curr) => acc + curr.duration, 0)
    });
    return {
      week: calc(activities.filter(a => a.timestamp >= startOfWeek)),
      month: calc(activities.filter(a => a.timestamp >= startOfMonth)),
      year: calc(activities.filter(a => a.timestamp >= startOfYear)),
      total: calc(activities)
    };
  }, [activities]);

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-white">
      <Loader2 className="animate-spin text-orange-500" size={48} />
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans pb-28">
      <header className="bg-white border-b sticky top-0 z-10 p-4 flex justify-between items-center shadow-sm">
        <h1 className="text-xl font-black flex items-center gap-2 tracking-tighter">
          <div className="bg-orange-500 p-1.5 rounded-lg"><Activity size={20} className="text-white" /></div> 
          FitTracker
        </h1>
        <div className="flex bg-slate-100 p-1 rounded-xl">
          <button onClick={() => setActiveTab('list')} className={`px-4 py-2 rounded-lg text-xs font-black uppercase transition-all ${activeTab === 'list' ? 'bg-white shadow-sm text-orange-600' : 'text-slate-500'}`}>Treningi</button>
          <button onClick={() => setActiveTab('summary')} className={`px-4 py-2 rounded-lg text-xs font-black uppercase transition-all ${activeTab === 'summary' ? 'bg-white shadow-sm text-orange-600' : 'text-slate-500'}`}>Raporty</button>
        </div>
      </header>

      {statusMsg && (
        <div className={`fixed top-24 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-2xl shadow-xl flex items-center gap-3 text-sm font-bold bg-emerald-500 text-white animate-in slide-in-from-top duration-300`}>
          <CheckCircle2 size={20} /> {statusMsg.text}
        </div>
      )}

      <main className="max-w-2xl mx-auto p-4">
        {activeTab === 'list' ? (
          <div className="space-y-4">
            {activities.length === 0 ? (
              <div className="text-center py-16 bg-white rounded-3xl border-2 border-dashed border-slate-200">
                <Activity size={40} className="text-slate-200 mx-auto mb-2" />
                <h3 className="text-slate-400 font-bold uppercase text-xs">Brak aktywności</h3>
              </div>
            ) : (
              activities.map((a) => (
                <div key={a.id} className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100 flex items-center gap-4 hover:shadow-md transition-shadow">
                  <div className={`${ACTIVITY_TYPES[a.type].bgColor} p-3 rounded-2xl`}><div className={ACTIVITY_TYPES[a.type].iconColor}>{React.createElement(ACTIVITY_TYPES[a.type].icon, { size: 24 })}</div></div>
                  <div className="flex-1">
                    <div className="flex justify-between items-center"><h3 className="font-black text-xs uppercase tracking-wider">{ACTIVITY_TYPES[a.type].label}</h3><span className="text-[10px] text-slate-400 font-bold">{a.date}</span></div>
                    <div className="flex gap-4 mt-1 text-sm font-bold text-slate-600"><span>{a.distance} km</span><span>{a.duration} min</span></div>
                  </div>
                  <button onClick={() => deleteActivity(a.id)} className="p-2 text-slate-200 hover:text-red-500 transition-colors"><Trash2 size={18} /></button>
                </div>
              ))
            )}
          </div>
        ) : (
          <div className="space-y-6">
            {/* AI Panel */}
            <section className="bg-gradient-to-br from-indigo-600 to-purple-700 p-6 rounded-[32px] text-white shadow-xl relative overflow-hidden">
               <div className="relative z-10">
                  <h2 className="text-lg font-black uppercase mb-4 flex items-center gap-2"><Sparkles size={22} className="text-amber-300" /> Inteligencja AI</h2>
                  <div className="flex gap-2">
                    <button onClick={generateAiAnalysis} disabled={isAiLoading} className="flex-1 bg-white/10 p-3 rounded-2xl text-xs font-bold border border-white/20 flex items-center justify-center gap-2">{isAiLoading ? <Loader2 size={16} className="animate-spin" /> : <Brain size={16} />} Analiza</button>
                    <button onClick={playMotivationalSpeech} disabled={isTtsLoading} className="flex-1 bg-white/10 p-3 rounded-2xl text-xs font-bold border border-white/20 flex items-center justify-center gap-2">{isTtsLoading ? <Loader2 size={16} className="animate-spin" /> : <Volume2 size={16} />} Motywacja</button>
                  </div>
                  {aiAnalysis && <div className="mt-4 bg-white/10 rounded-2xl p-4 border border-white/10 text-xs italic animate-in fade-in slide-in-from-bottom duration-300">"{aiAnalysis}"</div>}
               </div>
            </section>

            {/* Statystyki */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white p-5 rounded-3xl border border-slate-100 shadow-sm"><h3 className="text-[10px] font-black uppercase text-slate-400 mb-1">Tydzień</h3><div className="text-xl font-black tracking-tight">{stats.week.distance} km</div></div>
              <div className="bg-white p-5 rounded-3xl border border-slate-100 shadow-sm"><h3 className="text-[10px] font-black uppercase text-slate-400 mb-1">Miesiąc</h3><div className="text-xl font-black tracking-tight">{stats.month.distance} km</div></div>
              <div className="bg-white p-5 rounded-3xl border border-slate-100 shadow-sm"><h3 className="text-[10px] font-black uppercase text-slate-400 mb-1">Rok</h3><div className="text-xl font-black tracking-tight">{stats.year.distance} km</div></div>
              <div className="bg-white p-5 rounded-3xl border border-slate-100 shadow-sm"><h3 className="text-[10px] font-black uppercase text-slate-400 mb-1">Całość</h3><div className="text-xl font-black tracking-tight">{stats.total.distance} km</div></div>
            </div>

            {/* ZARZĄDZANIE DANYMI (ARCHIWIZACJA) */}
            <section className="bg-slate-900 text-white p-6 rounded-[32px] shadow-lg">
              <h2 className="text-lg font-black uppercase mb-4 flex items-center gap-2"><Cloud size={20} className="text-orange-400" /> Zarządzanie Danymi</h2>
              <div className="grid grid-cols-1 gap-3">
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={exportData} className="bg-slate-800 hover:bg-slate-700 p-4 rounded-2xl text-xs font-bold border border-slate-700 flex flex-col items-center gap-2">
                    <Download size={20} className="text-orange-400" /> Eksportuj JSON
                  </button>
                  <button onClick={copyDataToClipboard} className="bg-slate-800 hover:bg-slate-700 p-4 rounded-2xl text-xs font-bold border border-slate-700 flex flex-col items-center gap-2">
                    <Copy size={20} className="text-blue-400" /> Kopiuj kod
                  </button>
                </div>
                <button onClick={() => fileInputRef.current.click()} className="bg-slate-800 hover:bg-slate-700 p-4 rounded-2xl text-xs font-bold border border-slate-700 flex items-center justify-center gap-3">
                  <Upload size={20} className="text-emerald-400" /> Przywróć z pliku (Import)
                </button>
                <button 
                  onClick={() => setShowInstallGuide(true)}
                  className="bg-orange-500 hover:bg-orange-600 p-4 rounded-2xl text-xs font-black uppercase flex items-center justify-center gap-3 shadow-lg"
                >
                  <Smartphone size={20} /> Jak zainstalować?
                </button>
                <input type="file" ref={fileInputRef} onChange={importData} accept=".json" className="hidden" />
              </div>
              <div className="mt-4 flex items-center justify-center gap-2 text-[9px] font-black uppercase text-slate-500 tracking-widest">
                <ShieldCheck size={12} /> Synchronizacja w chmurze aktywna
              </div>
            </section>
          </div>
        )}
      </main>

      <button onClick={() => setShowAddModal(true)} className="fixed bottom-8 right-8 w-16 h-16 bg-orange-500 text-white rounded-full shadow-2xl flex items-center justify-center z-20 hover:scale-110 active:scale-90 transition-all shadow-orange-200"><Plus size={36} /></button>

      {showInstallGuide && (
        <div className="fixed inset-0 bg-slate-900/80 backdrop-blur-md flex items-center justify-center z-[100] p-4">
          <div className="bg-white w-full max-w-sm rounded-[40px] p-8 shadow-2xl">
            <h2 className="text-xl font-black mb-4 flex items-center gap-2"><Smartphone className="text-orange-500" /> Instalacja</h2>
            <div className="space-y-4 text-sm text-slate-600 leading-relaxed">
              <p>1. Kliknij przycisk <strong>Share</strong> (Udostępnij) w górnym menu platformy (nad oknem z kodem).</p>
              <p>2. Wyślij sobie ten link na telefon i otwórz go w przeglądarce.</p>
              <p>3. Na telefonie wybierz <strong>Menu</strong> i opcję <strong>"Dodaj do ekranu głównego"</strong>.</p>
            </div>
            <button onClick={() => setShowInstallGuide(false)} className="w-full mt-8 bg-slate-900 text-white font-black py-4 rounded-3xl uppercase tracking-widest text-xs">Zamknij</button>
          </div>
        </div>
      )}

      {/* Modal Dodawania */}
      {showAddModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-end sm:items-center justify-center z-50 p-4">
          <div className="bg-white w-full max-w-md rounded-t-[40px] sm:rounded-[40px] p-8 shadow-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-8">
              <h2 className="text-2xl font-black tracking-tight">Nowy trening</h2>
              <button onClick={() => setShowAddModal(false)} className="bg-slate-100 p-2 rounded-full text-slate-400 text-xl w-10 h-10 flex items-center justify-center">✕</button>
            </div>
            <form onSubmit={handleAddActivity} className="space-y-6">
              <div className="grid grid-cols-4 gap-2">
                {Object.entries(ACTIVITY_TYPES).map(([k, v]) => (
                  <button key={k} type="button" onClick={() => setFormData({...formData, type: k})} className={`p-2 rounded-xl border-2 transition-all flex flex-col items-center ${formData.type === k ? 'border-orange-500 bg-orange-50 text-orange-600 scale-105 shadow-sm' : 'border-slate-50 text-slate-300 hover:border-slate-100'}`}>
                    {React.createElement(v.icon, { size: 20 })}
                    <span className="text-[8px] mt-1 font-black uppercase truncate w-full text-center">{v.label}</span>
                  </button>
                ))}
              </div>
              <div className="space-y-4">
                <input type="date" value={formData.date} onChange={e => setFormData({...formData, date: e.target.value})} className="w-full bg-slate-50 rounded-2xl p-4 font-bold outline-none border-none text-slate-700" />
                <div className="grid grid-cols-2 gap-4">
                  <input type="number" step="0.1" placeholder="Km" value={formData.distance} onChange={e => setFormData({...formData, distance: e.target.value})} className="w-full bg-slate-50 rounded-2xl p-4 font-bold outline-none border-none" />
                  <input type="number" placeholder="Min" value={formData.duration} onChange={e => setFormData({...formData, duration: e.target.value})} className="w-full bg-slate-50 rounded-2xl p-4 font-bold outline-none border-none" />
                </div>
              </div>
              <button type="submit" className="w-full bg-orange-500 text-white font-black py-5 rounded-3xl shadow-xl shadow-orange-100 uppercase tracking-widest text-sm transition-transform active:scale-95">Zapisz trening</button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
