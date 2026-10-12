# CareerOS V1 — Rapport de validation production

- Date : 2026-10-12 · commit validé `02fa6dd` · branche `conflict_051026_2250`
- Backend : https://interview-ai-engine.onrender.com (Render) · Frontend : https://interview-ai-engine.pages.dev (Cloudflare Pages) · Base : MongoDB Atlas
- Statut : **production validée officiellement par le propriétaire — V1 gelée fonctionnellement**

## Résultats
| Domaine | Script | Résultat |
|---|---|---|
| Authentification (inscription, doublon 409, mot de passe court 422, login, mauvais mdp 401, sans jeton / jeton invalide / refresh-as-access 401, refresh, verrouillage 5 essais → 429) | `prod_auth.py` | 12/12 |
| MongoDB Atlas (écriture + lecture profil, Career Score stocké + historisé) | `prod_auth.py` | 5/5 |
| Isolation des membres (lecture, liste, statut, recruteur, version, archivage, profil) | `pack_iso.py` | 7/7 |
| Pack candidature (6 documents, 88 s, sans erreur) · code `CO-2026-000001` | `pack_iso.py` | OK |
| IPS : 10 critères aux poids officiels, points = poids × note / 10, somme 64 = IPS 64, priorité B conforme, critères déterministes (fraîcheur 10, réseau 6, lettre 8) | `pack_iso.py` | 7/7 |
| Decision Report (résumé, raison de priorité, forces, freins, actions) · version v1 immuable · ips_history · Career Score recalculé | `pack_iso.py` | 5/5 |
| Interface : connexion → tableau de bord → dossier ; exports PDF + DOCX (CV ATS, lettre) : nom `CO-2026-000001_*`, référence dans le document, accents OK | navigateur | 4/4 fichiers |

Fichiers d'export téléchargés depuis la production : `CO-2026-000001_CV-ATS.{pdf,docx}`, `CO-2026-000001_Lettre-de-motivation.{pdf,docx}` (dans `/app/memory/prod_validation/`).

## Constats et corrections post-validation (autorisées)
1. Decision Report : l'IA citait ses propres estimations d'IPS (« ~48/100 → ~68/100 ») ≠ IPS officiel 64.
   → Le prompt interdit toute valeur chiffrée ; filet déterministe qui retire toute phrase IA contenant un score/estimation ;
   le résumé commence toujours par « IPS officiel CareerOS : N/100 — priorité X. » ; impacts exprimés en mots ;
   les anciens rapports stockés sont re-dérivés à la lecture (stockage jamais réécrit).
2. /admin : affichage de débogage retiré ; messages de production propres ; le détail technique ne part plus que dans les logs serveur.

## Comptes de test créés en production
`validation+prod1791765658@careeros.dev`, `validation+iso…`, `validation+bf…` (mot de passe `ProdCheck2026!`) — à supprimer dans Atlas (`users`, `career_profiles`, `applications`, `application_versions`, `career_score_history`) si souhaité.

## Rejouer
`python3 prod_auth.py` (crée de nouveaux comptes + ctx.json) puis `python3 pack_iso.py` (≈ 6 appels IA).

## Validation finale post-publication — 2026-10-12 (bundle main.1b366b93.js)
| Contrôle | Résultat |
|---|---|
| /admin : aucun débogage dans le bundle, mauvais mot de passe → « Mot de passe administrateur incorrect », aucun bloc technique affiché | ✅ |
| Authentification : 3 connexions consécutives 200, /me 200, sans jeton 401 | ✅ |
| Decision Report CO-2026-000001 (existant) : v2, « IPS officiel CareerOS : 64/100 — priorité B. », aucune estimation IA chiffrée | ✅ |
| Nouveau pack CO-2026-000002 : 6 documents en 80 s, IPS 59 = somme des points, Decision Report officiel, aucune estimation IA | ✅ |
| Exports production CO-2026-000002 (CV ATS + lettre, PDF + DOCX) : nom avec code, référence dans le document, accents OK | ✅ |
`post_publish_check.py` : 17/17. **CareerOS V1 officiellement publié et gelé fonctionnellement.**
