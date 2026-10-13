export const GLOSSARY = {
  ips: { title: "IPS officiel CareerOS", text: "Indice de probabilité d'entrevue (0-100), calculé par une formule transparente sur 10 critères notés : profil, expérience, compétences, CV, lettre, réseau, etc." },
  ips_radar: { title: "IPS Radar", text: "Version provisoire de l'IPS, calculée sur les 8 critères évaluables avant de postuler (sans lettre ni réseau). L'IPS officiel est recalculé dans le pack." },
  priorite: { title: "Priorités A / B / C", text: "A : IPS ≥ 70 et objectifs ≥ 6/10, à prioriser. B : IPS ≥ 50, à étudier. C : à éviter, ou exigence éliminatoire détectée." },
  deep: { title: "Analyse approfondie", text: "Fait analyser l'offre par l'IA plutôt que par les règles. CareerOS le fait automatiquement pour les 5 meilleures offres du jour ; vous pouvez le demander pour d'autres." },
  regles: { title: "Pré-analyse par règles", text: "Comparaison sans IA entre votre Career Memory et l'offre : postes visés, compétences, années d'expérience, langues, lieu, exigences éliminatoires." },
  memory: { title: "Career Memory", text: "Votre profil de carrière permanent : CV, postes visés, ville, compétences, objectifs. Tout CareerOS s'appuie dessus, complétez-le en premier." },
  career_score: { title: "Career Score", text: "Indicateur global de votre progression : qualité de la Career Memory, IPS moyen, activité, résultats obtenus et développement du profil." },
  extrait: { title: "Analyse sur extrait", text: "L'agrégateur (Jooble) ne fournit qu'un extrait de l'offre : les critères non vérifiables reçoivent une note neutre. Ouvrez l'offre pour la lire en entier." },
  pack: { title: "Pack candidature", text: "En un clic : analyse ATS, IPS officiel, CV ATS et CV humain, lettre, questions d'entrevue, réponses STAR et simulation recruteur." },
  versions: { title: "Versions", text: "Chaque réanalyse crée une nouvelle version : rien n'est écrasé. Vous pouvez comparer l'évolution de l'IPS entre versions." },
  suivi: { title: "Suivi", text: "Brouillons d'e-mails (confirmation, remerciement, relance) et fichiers calendrier. Rien n'est envoyé ni ajouté sans votre validation." },
  ics: { title: "Fichier .ics", text: "Fichier calendrier compatible Google Agenda, Outlook et Apple Calendrier : ouvrez-le pour ajouter l'entrevue vous-même." },
};

export const TOUR = [
  { key: "memory", title: "1. Career Memory", time: "2 min", to: "/careeros/memoire", text: "Collez votre CV, indiquez vos postes visés et votre ville. C'est la base de toutes les analyses." },
  { key: "radar", title: "2. Radar", time: "3 min", to: "/careeros/radar", text: "CareerOS cherche les offres chaque matin (Jooble, Workday, sites carrières), les pré-analyse et les classe A / B / C." },
  { key: "pack", title: "3. Pack candidature", time: "5 min", to: "/careeros/nouveau", text: "Sur une offre retenue, générez le pack : CV adaptés, lettre, questions et IPS officiel expliqué." },
  { key: "interview", title: "4. Préparation d'entrevue", time: "5 min", to: "/careeros/copilote", text: "Entraînez-vous avec le Copilote : un recruteur virtuel vous pose les questions et commente vos réponses." },
  { key: "followup", title: "5. Suivi", time: "2 min", to: "/careeros", text: "Mettez à jour le statut, préparez remerciements et relances, exportez l'entrevue dans votre calendrier." },
];
