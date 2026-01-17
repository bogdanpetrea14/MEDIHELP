# Arhitectură Rețele și Securitate

## Analiză Situație Curentă

**Problema**: Toate serviciile sunt pe o singură rețea (`backend_net`), ceea ce înseamnă:
- Frontend poate accesa direct toate serviciile
- Serviciile pot accesa direct baza de date și Redis
- Monitoring poate accesa toate serviciile direct
- Fără izolare între componente

## Arhitectură Propusă: Rețele Fragmentate

### Rețelele necesare:

1. **`frontend_net`** - Frontend (izolat, comunică doar cu gateway)
2. **`gateway_net`** - Gateway (comunică cu frontend și servicii)
3. **`services_net`** - Servicii microservicii (user-profile, prescription, inventory, pharmacy)
4. **`database_net`** - PostgreSQL și Redis (doar serviciile pot accesa)
5. **`auth_net`** - Keycloak (doar gateway poate accesa)
6. **`monitoring_net`** - Prometheus și Grafana (pot accesa servicii pentru metrici)

### Matrice de Comunicare:

| Serviciu           | frontend_net | gateway_net | services_net | database_net | auth_net | monitoring_net |
|-------------------|--------------|-------------|--------------|--------------|----------|----------------|
| frontend-web      | ✓            | ✓           | ✗            | ✗            | ✗        | ✗              |
| gateway-service   | ✓            | ✓           | ✓            | ✗            | ✓        | ✗              |
| user-profile      | ✗            | ✗           | ✓            | ✓            | ✗        | ✓              |
| prescription      | ✗            | ✗           | ✓            | ✓            | ✗        | ✓              |
| inventory         | ✗            | ✗           | ✓            | ✓            | ✗        | ✓              |
| pharmacy          | ✗            | ✗           | ✓            | ✓            | ✗        | ✓              |
| postgres-db       | ✗            | ✗           | ✗            | ✓            | ✗        | ✓ (exporter)   |
| redis             | ✗            | ✗           | ✗            | ✓            | ✗        | ✓ (exporter)   |
| keycloak-service  | ✗            | ✗           | ✗            | ✗            | ✓        | ✗              |
| prometheus        | ✗            | ✗           | ✗            | ✗            | ✗        | ✓              |
| grafana           | ✗            | ✗           | ✗            | ✗            | ✗        | ✓              |

### Beneficii:

1. **Securitate crescută**: Fiecare serviciu poate comunica doar cu serviciile necesare
2. **Izolare**: Baza de date este izolată, accesibilă doar de servicii
3. **Principiul least privilege**: Fiecare serviciu are acces minim necesar
4. **Defense in depth**: Mai multe niveluri de securitate
