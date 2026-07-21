# Politique de sécurité

*[English version below](#security-policy)*

## Portée

FletchTime est pensé pour tourner sur un réseau local (WiFi de club), pas
exposé sur Internet -- ce contexte réduit fortement la surface d'attaque
par rapport à un service web classique. Ceci dit, une faille locale reste
une faille : merci de la signaler si tu en trouves une.

Sont notamment dans le périmètre :
- Contournement de l'authentification par mot de passe (`config/auth.toml`)
- Écriture ou lecture de fichiers en dehors des dossiers prévus
  (`config/`, `web/assets/`) via une commande ou une requête HTTP
- Déni de service trivial (une seule requête qui plante durablement le
  serveur, pas juste un tick manqué -- voir la résilience de
  `tick_loop`, déjà couverte)

Hors périmètre (comportement attendu, pas une faille) :
- Absence de chiffrement (HTTP/WS en clair) -- adapté à un réseau local de
  confiance, pas à un déploiement Internet
- Accès complet aux commandes de contrôle sans mot de passe configuré --
  c'est le réglage par défaut, documenté, pas un oubli

## Signaler une faille

**Ne pas** ouvrir une Issue publique pour une faille de sécurité tant
qu'elle n'est pas corrigée. Contacte plutôt le mainteneur directement :

- Via l'onglet **Security** du dépôt GitHub
  ([signaler une vulnérabilité](https://github.com/MrFanghoDev/fletchtime/security/advisories/new))
- Ou par le contact indiqué sur le profil GitHub du mainteneur

Merci d'inclure : les étapes pour reproduire, la version de FletchTime
concernée, et l'impact potentiel tel que tu le vois.

## À quoi s'attendre

Projet porté par un club, pas une entreprise avec une équipe sécurité
dédiée -- pas de délai de réponse garanti, mais chaque signalement sera
pris au sérieux. Une fois corrigée, la faille sera documentée dans les
notes de version, avec crédit à qui l'a signalée si souhaité.

---

# Security Policy

## Scope

FletchTime is designed to run on a local network (a club's WiFi), not
exposed to the Internet -- this context significantly reduces the attack
surface compared to a typical web service. That said, a local
vulnerability is still a vulnerability: please report it if you find one.

In scope:
- Bypassing password authentication (`config/auth.toml`)
- Reading or writing files outside the intended directories
  (`config/`, `web/assets/`) via a command or HTTP request
- Trivial denial of service (a single request that durably crashes the
  server, not just a missed tick -- see `tick_loop`'s resilience,
  already covered)

Out of scope (expected behavior, not a vulnerability):
- No encryption (plain HTTP/WS) -- suited to a trusted local network,
  not an Internet deployment
- Full access to control commands with no password configured -- that's
  the documented default, not an oversight

## Reporting a vulnerability

**Do not** open a public Issue for a security vulnerability until it's
fixed. Instead, contact the maintainer directly:

- Via the repository's **Security** tab
  ([report a vulnerability](https://github.com/MrFanghoDev/fletchtime/security/advisories/new))
- Or through the contact listed on the maintainer's GitHub profile

Please include: steps to reproduce, the FletchTime version affected, and
the potential impact as you see it.

## What to expect

This project is run by a club, not a company with a dedicated security
team -- no guaranteed response time, but every report will be taken
seriously. Once fixed, the issue will be documented in the release notes,
with credit to the reporter if desired.
