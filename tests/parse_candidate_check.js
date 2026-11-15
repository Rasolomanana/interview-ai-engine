const {parseCandidate}=require('/tmp/pt/parse.cjs') /* generate via: sed 's/^export //' frontend/src/lib/parse.js > /tmp/pt/parse.cjs + module.exports */;
const a=parseCandidate("🌐 FR : Parlez-moi d'un conflit\n• **Situation**: team conflict\n• Action: I mediated\n• 🌐 TRAD : J'ai géré un conflit");
console.log(JSON.stringify(a));
const b=parseCandidate("• Réponse FR\n🌐 TRAD : traduction");console.log(JSON.stringify(b));
const c=parseCandidate("• Je suis\n• Bien");console.log(JSON.stringify(c));
const d=parseCandidate("• 🌐 FR : question");console.log(JSON.stringify(d));
