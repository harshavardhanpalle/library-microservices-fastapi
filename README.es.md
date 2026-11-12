# 🐳 Microservicios de Biblioteca: FastAPI, PostgreSQL y Nginx con Docker Compose

[![CI](https://img.shields.io/github/actions/workflow/status/aledash3/library-microservices-fastapi/ci.yml?branch=main&style=for-the-badge&logo=github-actions&logoColor=white)](https://github.com/aledash3/library-microservices-fastapi/actions)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Nginx](https://img.shields.io/badge/Nginx-API%20Gateway-009639?style=for-the-badge&logo=nginx&logoColor=white)](https://nginx.org/)
[![Tests](https://img.shields.io/badge/Tests-46%20Passed-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Licencia: MIT](https://img.shields.io/badge/Licencia-MIT-yellow?style=for-the-badge)](LICENSE)
[![English](https://img.shields.io/badge/Language-English-blue?style=for-the-badge)](README.md)

Arquitectura de microservicios con FastAPI, persistencia en PostgreSQL, Nginx como API Gateway y redes internas aisladas con Docker Compose.

> 🌐 **Language / Idioma:** Español | [Switch to English documentation](README.md)

---

## Alcance y limitaciones

Proyecto académico. Nginx enruta peticiones a un único upstream por servicio; la configuración actual no demuestra balanceo entre réplicas. Los servicios comparten PostgreSQL: simplifica el ejercicio, pero acopla la capa de datos. Las redes internas y el endurecimiento de contenedores no bastan para declarar el sistema listo para producción. Para un despliegue real deben evaluarse autenticación, TLS, monitoreo, respaldos/restauración y pruebas de carga.

CI se ejecuta actualmente en Python 3.11 y 3.12. El workflow y la salida de las pruebas son la referencia; un contador fijo de pruebas no garantiza cobertura.

## 📌 Descripción General

Este repositorio contiene la implementación de una arquitectura de microservicios contenerizada orientada a la gestión de una biblioteca digital, construida con **Docker Compose**, **FastAPI**, **PostgreSQL** y **Nginx**.

El sistema está compuesto por tres microservicios desacoplados:

* `books_service`: Catálogo y gestión integral de libros.
* `users_service`: Registro y administración de usuarios.
* `orders_service`: Gestión de préstamos y órdenes vinculando usuarios y libros.

Todos los servicios se ejecutan en contenedores independientes y se comunican a través de redes internas protegidas. La base de datos PostgreSQL permanece estrictamente aislada del host exterior, mientras que **Nginx** actúa como **API Gateway** y reverse proxy inverso, ofreciendo un único punto de entrada HTTP.

El proyecto implementa **operaciones CRUD completas**, documentación interactiva mediante **Swagger UI**, persistencia de datos mediante volúmenes Docker nombrados, control estricto de seguridad en contenedores (`read_only`, `cap_drop: ALL`, usuarios no-root) y una suite completa de pruebas automatizadas con integración continua (CI).

---

## 🎯 Objetivos

### Objetivo General
Diseñar y desplegar una arquitectura de microservicios robusta, segura y escalable utilizando FastAPI, PostgreSQL, Docker Compose y Nginx, aplicando principios de mínimo privilegio, aislamiento de redes y persistencia de datos.

### Objetivos Específicos
* Desarrollar tres microservicios RESTful independientes con FastAPI.
* Implementar operaciones CRUD completas y validaciones con Pydantic.
* Configurar PostgreSQL como almacén relacional centralizado con comprobaciones de estado (`healthchecks`).
* Orquestar la infraestructura multicontenedor mediante Docker Compose.
* Diseñar un API Gateway con Nginx para el enrutamiento transparente de rutas hacia los microservicios.
* Aislar la red de datos mediante subredes Docker internas (`internal: true`).
* Gestionar secretos y configuración mediante `.env` y plantilla `.env.example`.
* Asegurar contenedores con sistema de archivos de solo lectura, usuarios sin privilegios y eliminación de capacidades del kernel de Linux.
* Implementar pruebas unitarias y de integración automatizadas con Pytest e Integración Continua (CI) en GitHub Actions.

---

## 🧱 Arquitectura del Sistema

<p align="center">
  <img src="docs/assets/architecture.svg" alt="Topología de Arquitectura de Microservicios" width="100%">
</p>

La arquitectura sigue el patrón de diseño de microservicios desacoplados con un Gateway perimetral:

```text
Cliente / Frontend / curl
         │
         ▼  (Puerto :8080 en host)
┌───────────────────────────────────────┐
│        Nginx API Gateway              │  Network: public_net (bridge)
└──────────────────┬────────────────────┘
                   │
                   ▼  (Enrutamiento interno)
┌───────────────────────────────────────┐
│              app_net                  │  Network: app_net (internal: true)
│   ┌──────────────┬────────────────┐   │
│   ▼              ▼                ▼   │
│ Books Service  Users Service   Orders │
│  (:5000)        (:5000)       (:5000) │
└──────────────────┬────────────────────┘
                   │
                   ▼  (Consultas SQL)
┌───────────────────────────────────────┐
│              db_net                   │  Network: db_net (internal: true)
│   ┌───────────────────────────────┐   │
│   │   PostgreSQL 13 (db:5432)     │   │
│   │   Volume: postgres_data       │   │
│   └───────────────────────────────┘   │
└───────────────────────────────────────┘
```

* **Único punto de acceso expuesto**: Únicamente el puerto `8080` de Nginx está mapeado hacia el host.
* **Aislamiento perimetral**: Ni los microservicios ni PostgreSQL exponen puertos al exterior, evitando vectores de ataque directos.
* **Resiliencia**: Los microservicios esperan automáticamente a que PostgreSQL esté `healthy` antes de iniciar.

---

## 🗂️ Estructura del Proyecto

```text
├── .github/
│   └── workflows/
│       └── ci.yml                 # Pipeline CI GitHub Actions (Python 3.11, 3.12)
├── books_service/
│   ├── .dockerignore              # Exclusiones de contexto Docker
│   ├── app.py                     # API FastAPI y lógica de base de datos
│   ├── Dockerfile                 # Imagen no-root basada en python:3.11-slim
│   └── requirements.txt           # Dependencias de producción
├── nginx/
│   └── nginx.conf                 # Configuración del Gateway y proxy inverso
├── orders_service/
│   ├── .dockerignore
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Fixtures, clientes de prueba y mocks de conexión
│   ├── test_books_service.py      # Pruebas unitarias de Books Service
│   ├── test_docker_compose.py     # Verificación de sintaxis y seguridad de Compose
│   ├── test_nginx_config.py       # Verificación de reglas Nginx
│   ├── test_orders_service.py     # Pruebas unitarias de Orders Service
│   └── test_users_service.py       # Pruebas unitarias de Users Service
├── users_service/
│   ├── .dockerignore
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── .env.example                   # Plantilla de variables de entorno
├── .gitignore                     # Exclusión de credenciales y temporales
├── docker-compose.yml             # Orquestación de servicios, redes y volúmenes
├── LICENSE                        # Licencia MIT
├── pyproject.toml                 # Configuración de herramientas (Pytest, Ruff)
├── README.es.md                   # Documentación en Español
└── README.md                      # Documentación en Inglés
```

---

## 🛠️ Tecnologías Utilizadas

| Tecnología | Versión | Rol en el Sistema |
| :--- | :--- | :--- |
| **Python** | 3.11+ | Lenguaje base para los microservicios backend |
| **FastAPI** | 0.115.0 | Framework ASGI moderno y de alto rendimiento para APIs REST |
| **Uvicorn** | 0.30.6+ | Servidor web ASGI de producción |
| **PostgreSQL** | 13 | Sistema de gestión de bases de datos relacional |
| **Psycopg2** | 2.9.9 | Adaptador nativo de PostgreSQL para Python |
| **Docker** | 24+ | Contenerización ligera de cada componente |
| **Docker Compose**| v2+ | Orquestación declarativa de redes, servicios y volúmenes |
| **Nginx** | 1.25-alpine | API Gateway perimetral y proxy inverso |
| **Pytest** | 9.0+ | Framework de pruebas automatizadas con cobertura |
| **Ruff** | 0.15+ | Linter y analizador estático ultrarrápido |
| **Swagger UI** | Integrado | Documentación interactiva de APIs REST |

---

## 🧩 Microservicios y Endpoints

### 📚 1. Books Service (`/api/books`)

Administra el catálogo bibliográfico.

* **Esquema de Entrada (`BookCreate` / `BookUpdate`)**:
  ```json
  {
    "title": "Cien años de soledad",
    "author": "Gabriel García Márquez"
  }
  ```

| Método | Endpoint | Descripción | Código Éxito |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/books/` | Lista todos los libros registrados | `200 OK` |
| `GET` | `/api/books/{id}` | Obtiene un libro específico por su identificador | `200 OK` |
| `POST` | `/api/books/` | Registra un nuevo libro en el catálogo | `201 Created` |
| `PUT` | `/api/books/{id}` | Actualiza título o autor de un libro existente | `200 OK` |
| `DELETE` | `/api/books/{id}` | Elimina un libro (valida integridad con órdenes) | `200 OK` |
| `GET` | `/api/books/health` | Comprobación de salud del servicio | `200 OK` |
| `GET` | `/api/books/docs` | Documentación Swagger UI interactiva | `200 OK` |

> [!NOTE]
> Si se intenta eliminar un libro que posee órdenes activas asociadas, el servicio responde con `409 Conflict` preservando la integridad referencial.

---

### 👤 2. Users Service (`/api/users`)

Gestiona el directorio de usuarios y lectores.

* **Esquema de Entrada (`UserCreate` / `UserUpdate`)**:
  ```json
  {
    "name": "David Cruz",
    "email": "david.cruz@example.com"
  }
  ```

| Método | Endpoint | Descripción | Código Éxito |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/users/` | Lista todos los usuarios registrados | `200 OK` |
| `GET` | `/api/users/{id}` | Consulta información de un usuario específico | `200 OK` |
| `POST` | `/api/users/` | Da de alta un nuevo usuario (valida email único) | `201 Created` |
| `PUT` | `/api/users/{id}` | Actualiza nombre o email de un usuario | `200 OK` |
| `DELETE` | `/api/users/{id}` | Elimina un usuario (valida integridad con órdenes) | `200 OK` |
| `GET` | `/api/users/health` | Comprobación de salud del servicio | `200 OK` |
| `GET` | `/api/users/docs` | Documentación Swagger UI interactiva | `200 OK` |

> [!IMPORTANT]
> El correo electrónico cuenta con restricción `UNIQUE` en la base de datos y validación de formato por expresiones regulares. Los duplicados devuelven `409 Conflict`.

---

### 🧾 3. Orders Service (`/api/orders`)

Modela los préstamos y pedidos relacionando usuarios con libros.

* **Esquema de Entrada (`OrderCreate` / `OrderUpdate`)**:
  ```json
  {
    "user_id": 1,
    "book_id": 1,
    "quantity": 2
  }
  ```

| Método | Endpoint | Descripción | Código Éxito |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/orders/` | Lista todas las órdenes con datos cruzados de libro y usuario | `200 OK` |
| `GET` | `/api/orders/{id}` | Consulta el detalle completo de una orden | `200 OK` |
| `POST` | `/api/orders/` | Registra una orden (valida existencia previa de usuario y libro) | `201 Created` |
| `PUT` | `/api/orders/{id}` | Modifica una orden existente | `200 OK` |
| `DELETE` | `/api/orders/{id}` | Cancela y elimina una orden | `200 OK` |
| `GET` | `/api/orders/health` | Comprobación de salud del servicio | `200 OK` |
| `GET` | `/api/orders/docs` | Documentación Swagger UI interactiva | `200 OK` |

---

## 🌐 API Gateway con Nginx

Nginx opera como el punto único de contacto perimetral. Cada solicitud entrante en el puerto `8080` es analizada y redirigida según su prefijo de ruta:

```nginx
upstream books_backend  { server books_service:5000; }
upstream users_backend  { server users_service:5000; }
upstream orders_backend { server orders_service:5000; }

server {
    listen 80;
    server_tokens off;

    location /api/books/  { proxy_pass http://books_backend/;  ... }
    location /api/users/  { proxy_pass http://users_backend/;  ... }
    location /api/orders/ { proxy_pass http://orders_backend/; ... }
}
```

* **Ocultamiento de versión**: `server_tokens off;` previene la divulgación de versión en cabeceras HTTP.
* **Propagación de prefijo**: La cabecera `X-Forwarded-Prefix` asegura que FastAPI y Swagger UI resuelvan rutas relativas y OpenAPI specs correctamente.

---

## 🧪 Documentación Interactiva (Swagger UI)

Cada microservicio expone su propia documentación OpenAPI interactiva:

* **Libros**: `http://localhost:8080/api/books/docs`
* **Usuarios**: `http://localhost:8080/api/users/docs`
* **Órdenes**: `http://localhost:8080/api/orders/docs`

Permite explorar los esquemas JSON de petición/respuesta y ejecutar llamadas en vivo directamente desde el navegador.

---

## ⚙️ Requisitos Previos

* **Docker Engine** 24.0 o superior.
* **Docker Compose** v2 o superior.
* **Git** para clonar el repositorio.
* Opcional (para desarrollo local sin Docker): **Python 3.11+**.

---

## 🚀 Guía de Despliegue y Ejecución

### 1. Clonar el repositorio
```bash
git clone https://github.com/aledash3/library-microservices-fastapi.git
cd library-microservices-fastapi
```

### 2. Configurar variables de entorno
Copiar el archivo de plantilla `.env.example` a `.env`:
```bash
cp .env.example .env
```

Contenido de referencia del `.env`:
```env
POSTGRES_DB=library_db
POSTGRES_USER=library_user
POSTGRES_PASSWORD=library_password_secure123

DB_HOST=db
DB_PORT=5432

NGINX_HOST_PORT=8080
```

### 3. Construir y levantar la arquitectura
```bash
docker compose up --build -d
```

### 4. Verificar el estado de los contenedores
```bash
docker compose ps
```

Salida esperada (todos los contenedores `Up` y `db` en estado `healthy`):
```text
NAME                                  STATUS                    PORTS
biblioteca-db-1                       Up (healthy)              5432/tcp
biblioteca-books_service-1            Up                        5000/tcp
biblioteca-users_service-1            Up                        5000/tcp
biblioteca-orders_service-1           Up                        5000/tcp
biblioteca-nginx-1                    Up                        0.0.0.0:8080->80/tcp
```

---

## 🔬 Verificación con `curl`

### Verificación de Salud
```bash
curl http://localhost:8080/api/books/health
curl http://localhost:8080/api/users/health
curl http://localhost:8080/api/orders/health
```

### Flujo Completo de Pruebas CRUD

#### 1. Crear un usuario
```bash
curl -i -X POST http://localhost:8080/api/users/ \
  -H "Content-Type: application/json" \
  -d '{"name":"David Cruz","email":"david.cruz@example.com"}'
```

#### 2. Crear un libro
```bash
curl -i -X POST http://localhost:8080/api/books/ \
  -H "Content-Type: application/json" \
  -d '{"title":"El Principito","author":"Antoine de Saint-Exupéry"}'
```

#### 3. Crear una orden de préstamo
```bash
curl -i -X POST http://localhost:8080/api/orders/ \
  -H "Content-Type: application/json" \
  -d '{"user_id":1,"book_id":1,"quantity":2}'
```

#### 4. Consultar la orden con datos relacionales combinados
```bash
curl http://localhost:8080/api/orders/1
```

Respuesta devuelta:
```json
{
  "id": 1,
  "user_id": 1,
  "user_name": "David Cruz",
  "book_id": 1,
  "book_title": "El Principito",
  "quantity": 2,
  "created_at": "2026-06-22 18:00:00"
}
```

#### 5. Intentar eliminar un libro con órdenes (Protección de Integridad)
```bash
curl -i -X DELETE http://localhost:8080/api/books/1
```
> Retorna HTTP `409 Conflict` con el mensaje `"No se puede eliminar el libro porque tiene órdenes asociadas"`.

#### 6. Eliminar la orden y posteriormente el libro
```bash
curl -i -X DELETE http://localhost:8080/api/orders/1
curl -i -X DELETE http://localhost:8080/api/books/1
```
> Ambas operaciones retornan HTTP `200 OK`.

---

## 🗄️ Inspección Directa en PostgreSQL

Para consultar la base de datos de manera interactiva desde el contenedor:
```bash
docker compose exec db psql -U library_user -d library_db
```

Comandos útiles en `psql`:
```sql
-- Listar las tablas del sistema
\dt

-- Consultar registros de cada servicio
SELECT * FROM books;
SELECT * FROM users;
SELECT * FROM orders;

-- Salir de psql
\q
```

---

## 🛡️ Buenas Prácticas de Seguridad y DevOps

* **Principio de Mínimo Privilegio**: Las imágenes Docker crean y ejecutan el proceso bajo un usuario no-root (`appuser`).
* **Kernel Hardening**:
  * `read_only: true`: Los contenedores operan con sistema de archivos inmutable en tiempo de ejecución.
  * `cap_drop: - ALL`: Se revocan todas las capacidades innecesarias del kernel de Linux.
  * `security_opt: - no-new-privileges:true`: Se previene la escalada de privilegios mediante ejecutables con SUID.
  * `tmpfs: - /tmp`: Espacio temporal volátil en memoria RAM para operaciones temporales del sistema.
* **Aislamiento de Redes (`internal: true`)**:
  * `public_net`: Puente público que únicamente conecta a Nginx con el host.
  * `app_net`: Red interna protegida entre Nginx y los microservicios.
  * `db_net`: Red interna aislada exclusivamente para la comunicación con PostgreSQL.
* **Persistencia Segura**: Volumen Docker nombrado `postgres_data` para proteger los datos contra recreaciones o reinicios de contenedores.
* **Gestión de Secretos**: Ninguna contraseña sensible se versiona en el repositorio; se utiliza `.env` ignorado en `.gitignore`.

---

## 🧪 Pruebas Automatizadas e Integración Continua (CI)

<p align="center">
  <img src="docs/assets/test_preview.svg" alt="Resumen de Pruebas Automatizadas Pytest" width="100%">
</p>

El proyecto cuenta con una suite completa de **46 pruebas unitarias e integrales** que validan:
* Respuestas de endpoints y códigos HTTP.
* Validaciones de esquema Pydantic y reglas de negocio.
* Manejo de concurrencia y reintentos de conexión a base de datos.
* Detección de integridad referencial cruzada (conflictos 409).
* Estructura declarativa de `docker-compose.yml` y directivas de seguridad Nginx.

### Ejecución de Pruebas Localmente
```bash
# Instalar dependencias de pruebas
pip install pytest pytest-cov ruff pyyaml httpx

# Ejecutar suite de pruebas con reporte de cobertura
pytest --cov=. --cov-report=term-missing

# Ejecutar analizador de código estático (linter)
ruff check .
```

### Pipeline de Integración Continua (GitHub Actions)
Cada `push` o `pull request` en la rama `main` dispara automáticamente el workflow de CI en entornos Ubuntu con **Python 3.11 y 3.12**, garantizando máxima compatibilidad y calidad de código.

---

## 🧰 Comandos de Mantenimiento

```bash
# Inspeccionar logs de todos los contenedores en tiempo real
docker compose logs -f

# Inspeccionar logs de un servicio particular
docker compose logs -f books_service

# Detener los servicios preservando los datos de PostgreSQL
docker compose down

# Detener los servicios y reiniciar la base de datos desde cero
docker compose down -v

# Reconstruir imágenes forzando descarga y sin caché
docker compose up --build --force-recreate -d
```

---

## 👨‍💻 Autor

**David Alejandro Cruz Palacios**  
Estudiante de Ingeniería en Ciencias de la Computación — Universidad Politécnica Salesiana  
GitHub: [@aledash3](https://github.com/aledash3)  
Materia: Sistemas Distribuidos (6to Semestre)

---

## 📄 Licencia

Este proyecto está distribuido bajo la [Licencia MIT](LICENSE). Consulta el archivo `LICENSE` para más detalles.
