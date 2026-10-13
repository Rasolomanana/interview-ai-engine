import { MoreHorizontal } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

// items: [{ label, icon, onClick, href, danger, testid }] — destructive items are always listed last, after a separator
export const MoreMenu = ({ items, testid = "more-menu-btn" }) => {
  const list = items.filter(Boolean);
  if (!list.length) return null;
  const safe = list.filter((i) => !i.danger);
  const danger = list.filter((i) => i.danger);
  const row = (i) => {
    const Icon = i.icon;
    const inner = <>{Icon && <Icon className="h-3.5 w-3.5" />}{i.label}</>;
    return (
      <DropdownMenuItem key={i.label} onClick={i.onClick} asChild={!!i.href} data-testid={i.testid}
        className={`flex cursor-pointer items-center gap-2 text-xs ${i.danger ? "text-rose-300 focus:text-rose-200" : "text-slate-200"}`}>
        {i.href ? <a href={i.href} target="_blank" rel="noreferrer">{inner}</a> : inner}
      </DropdownMenuItem>
    );
  };
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center gap-1 rounded-full px-2.5 py-1.5 text-xs text-slate-400 hover:bg-white/5 hover:text-white" data-testid={testid} title="Plus d'actions"><MoreHorizontal className="h-4 w-4" />Plus</button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-52 border-white/10 bg-[#121520]">
        {safe.map(row)}
        {safe.length > 0 && danger.length > 0 && <DropdownMenuSeparator className="bg-white/10" />}
        {danger.map(row)}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
