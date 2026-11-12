# Yantra web development and deployment

## Create and run a project

Choose **वेब** under **ऐप का प्रकार** in **फ़ाइल → नई परियोजना**. Set the ports for
**dev**, **staging**, and **prod**. Edit `परिवेश.json` later to change ports or add a
named profile. Profiles hold public build settings. Supply secrets on the server
through its environment or secret manager.

The starter includes a Bhash HTTP server in `मुख्य.bhash`, a browser client in
`index.html` and `assets/`, a UTF-8 JSON API, parameterized SQLite queries, and a `/health`
endpoint. New and imported `.bhash` files under the project are picked up on each
build. The browser uses same-origin `fetch` for create, read, update, and delete.
Extend server routes for new features and use Bhash's
[HTTP and HTTPS client](https://github.com/bhashitva/bhash/blob/main/docs/networking.md)
for outbound service calls. Keep database credentials and service tokens on the
server. Put public resources in `assets/`. Yantra copies them into the bundle.
Register routes explicitly in Bhash, or serve the files through your web
server. The starter registers two fixed routes for its CSS and JavaScript.

Select **वेब → स्थानीय सर्वर चलाएँ** with Java 21 and a Bhash compiler configured
in **औज़ार सेटिंग**. The development server listens on loopback. After startup,
select **वेब → ब्राउज़र में खोलें**. Development SQLite data is stored in
`.studio/web-data/dev` and survives rebuilding. **वेब → वेब काम रोकें** ends the
session. Compiler and server output paths appear in the message panel.

## Export a deployment

Use **वेब → तैनाती बंडल बनाएँ…** and choose a profile. The printed directory
contains `app.jar`, `index.html`, `assets/`, and a `Dockerfile`. The container uses Java 21,
binds to its profile port, runs as UID/GID 10001, and stores SQLite under
`/data`. Build and run the default staging bundle from that directory:

```sh
docker build -t yantra-web:staging .
docker volume create yantra-web-staging-data
docker run --rm -p 127.0.0.1:8081:8081 \
  -v yantra-web-staging-data:/data yantra-web:staging
curl -f http://127.0.0.1:8081/health
```

Use separate staging and production volumes, environment variables, and
credentials. The export is portable and is handed off to the operator or CI/CD
pipeline for registry upload, deployment, and rollback. A plain Java deployment
can run the JAR alongside the HTML with `--host`, `--port`, `--db`, and
`--page` arguments. Give the service identity write access to its database
directory.

The task board is a single-user example. For an enterprise deployment, add
authentication, authorization, migrations, and tests for your application's
concurrency and failure modes. Terminate HTTPS at the ingress or reverse proxy.
Use the [Bhash HTTP runtime contract](https://github.com/bhashitva/bhash/blob/main/docs/web-applications.md)
to assess handler concurrency, request limits, and graceful shutdown before
selecting a production topology. Multi-replica applications need a suitable
shared data store and a coordinated migration process.

## Source-level debugging

- The starter's HTML and JavaScript can be debugged today with browser DevTools.
  Set breakpoints in Sources and inspect the requests in Network.
- Bhash's native backend emits original `.bhash` locations and DWARF with
  `--target native --debug`. The project already documents a
  [VS Code and GDB integration](https://github.com/bhashitva/bhash/blob/main/docs/native-vscode-debug.md).
  A Yantra integration can reuse that approach through the Debug Adapter
  Protocol and map temporary build source paths back to project tabs.
- The Yantra web workflow currently builds a JVM JAR. In a Bhash 0.25.0
  starter build, `javap -v` showed line tables for `BhashProgram.java` and no
  source mapping attribute on the entry-point class. Original-source JVM
  breakpoints, stepping, and variable inspection need a verified compiler
  mapping and a debugger adapter. Bhash compiled to WebAssembly would also
  require a verified source mapping and compatible browser debugger.

## Production logs

The starter emits a structured startup event through `मानक.लेखा`. Its
container sends application output to standard output and standard error. The
local Yantra run captures both in `server.log`. Use
[`लेखा.घटनालिखो`](https://github.com/bhashitva/bhash/blob/main/docs/application-foundations.md#configuration-logging-and-assertions)
for application events. Configure access logs at ingress for method, route,
status and latency, and propagate a request ID into application events.

In production, collect logs through the hosting runtime or an OpenTelemetry
collector. Set retention and rotation there. Include service, environment and
release metadata and correlate logs with trace IDs when tracing is enabled.
Keep tokens, cookies, request bodies and sensitive query strings out of logs.
Live production log access in Yantra would require a connector to the selected
logging backend and its access controls.
