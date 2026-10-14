import { useCallback, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { adminFinanceCatalog } from "@/lib/api";
import { pwd } from "./catalogUi";
import { CatalogCategories } from "./CatalogCategories";
import { CatalogProviders } from "./CatalogProviders";

export const CatalogSheet = ({ open, onClose }) => {
  const [data, setData] = useState(null);
  const load = useCallback(() => adminFinanceCatalog(pwd()).then(setData).catch((e) => toast.error(e.message)), []);
  useEffect(() => { if (open) load(); }, [open, load]);
  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto border-white/10 bg-slate-950 text-slate-200 sm:max-w-2xl" data-testid="catalog-sheet">
        <SheetHeader>
          <SheetTitle className="text-white">Catégories et fournisseurs</SheetTitle>
          <SheetDescription>Suppression possible seulement sans historique ; sinon archivez (l'historique reste visible dans les rapports).</SheetDescription>
        </SheetHeader>
        {!data ? <Loader2 className="mt-4 h-5 w-5 animate-spin text-emerald-400" /> : (
          <div className="mt-4 space-y-6">
            <CatalogCategories data={data} reload={load} />
            <CatalogProviders data={data} reload={load} />
          </div>)}
      </SheetContent>
    </Sheet>
  );
};
