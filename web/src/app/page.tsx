import AIStylist from "@/components/AIStylist";

export default function Home() {
  return (
    <main className="min-h-screen bg-[#f3f4f6] relative overflow-hidden flex flex-col font-sans">
      {/* Background decorations */}
      <div className="absolute top-[-10%] left-[-10%] w-96 h-96 bg-purple-300 rounded-full mix-blend-multiply filter blur-[128px] opacity-50 animate-blob"></div>
      <div className="absolute top-[20%] right-[-10%] w-96 h-96 bg-pink-300 rounded-full mix-blend-multiply filter blur-[128px] opacity-50 animate-blob animation-delay-2000"></div>
      <div className="absolute bottom-[-20%] left-[20%] w-96 h-96 bg-blue-300 rounded-full mix-blend-multiply filter blur-[128px] opacity-50 animate-blob animation-delay-4000"></div>

      {/* Header */}
      <header className="w-full p-6 z-10 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 bg-black rounded-xl flex items-center justify-center text-white font-bold text-xl">
            3D
          </div>
          <span className="font-bold text-xl tracking-tight text-gray-900">AI Stylist</span>
        </div>
        <nav className="flex flex-wrap justify-end gap-2 text-xs font-bold">
          <a href="/sessions" className="rounded-full bg-slate-950 px-3 py-2 text-white">Session Workspace</a>
          <a href="/review" className="rounded-full border border-slate-300 bg-white px-3 py-2 text-slate-700">Reviewer Queue</a>
          <a href="/admin" className="rounded-full border border-slate-300 bg-white px-3 py-2 text-slate-700">Admin Outbox</a>
        </nav>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex items-center justify-center p-4 z-10 w-full mb-12">
        <AIStylist />
      </div>

    </main>
  );
}
