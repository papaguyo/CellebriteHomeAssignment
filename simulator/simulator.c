/*
 * Device Simulator – Cellebrite home assignment
 *
 * A minimal TCP server that pretends to be a locked mobile device.
 * One connection is handled at a time (sequential accept loop).
 *
 * Protocol: newline-terminated text commands, JSON responses.
 * Binary payload for READ: JSON size header line, then raw bytes.
 *
 * CLI flags:
 *   --port      <port>       TCP port to listen on (default 9000)
 *   --model     <string>     device model identifier (default "iPhone14,2")
 *   --ios       <string>     iOS version string (default "16.5")
 *   --battery   <int>        battery percentage (default 80)
 *   --locked    <0|1>        is_locked flag (default 1)
 *   --fail-stage  <n>        force stage index n to return FAIL (-1 = none)
 *   --drop-after-stage <n>   drop TCP connection after completing stage n (-1 = never)
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <dirent.h>
#include <sys/stat.h>

#ifdef _WIN32
  #include <winsock2.h>
  #pragma comment(lib, "ws2_32.lib")
  typedef int socklen_t;
  #define close closesocket
#else
  #include <unistd.h>
  #include <arpa/inet.h>
  #include <sys/socket.h>
#endif

#define MAX_LINE   4096
#define MAX_PATH   1024
#define BACKLOG    4

/* ------------------------------------------------------------------ */
/* Configuration                                                        */
/* ------------------------------------------------------------------ */

typedef struct {
    int   port;
    char  model[64];
    char  ios_version[16];
    int   battery;
    int   is_locked;
    int   fail_stage;        /* -1 = never */
    int   drop_after_stage;  /* -1 = never */
    char  sim_files[MAX_PATH]; /* root dir, empty = use hardcoded tree */
} Config;

static Config cfg = {
    .port            = 9000,
    .model           = "iPhone14,2",
    .ios_version     = "16.5",
    .battery         = 80,
    .is_locked       = 1,
    .fail_stage      = -1,
    .drop_after_stage = -1,
    .sim_files       = "",
};

/* ------------------------------------------------------------------ */
/* Hardcoded in-memory file tree (used when --sim-files not set)       */
/* ------------------------------------------------------------------ */

typedef struct { const char *path; const char *content; } FakeFile;

static FakeFile fake_files[] = {
    { "/contacts.db",          "SQLITE3 contacts data" },
    { "/media/photo1.jpg",     "JPEG binary data placeholder" },
    { "/media/photo2.jpg",     "JPEG binary data placeholder 2" },
    { "/logs/system.log",      "system boot log line 1\nsystem boot log line 2\n" },
    { NULL, NULL }
};

/* ------------------------------------------------------------------ */
/* I/O helpers                                                          */
/* ------------------------------------------------------------------ */

static int send_all(int fd, const char *buf, size_t len) {
    size_t sent = 0;
    while (sent < len) {
        ssize_t n = send(fd, buf + sent, len - sent, 0);
        if (n <= 0) return -1;
        sent += (size_t)n;
    }
    return 0;
}

static int send_line(int fd, const char *line) {
    if (send_all(fd, line, strlen(line)) < 0) return -1;
    return send_all(fd, "\n", 1);
}

/* Read until '\n'; returns bytes read (including '\n'), 0 on EOF, -1 on error */
static int recv_line(int fd, char *buf, int maxlen) {
    int total = 0;
    while (total < maxlen - 1) {
        char c;
        ssize_t n = recv(fd, &c, 1, 0);
        if (n < 0) return -1;
        if (n == 0) return 0;
        buf[total++] = c;
        if (c == '\n') break;
    }
    buf[total] = '\0';
    return total;
}

/* ------------------------------------------------------------------ */
/* Command handlers                                                     */
/* ------------------------------------------------------------------ */

static void handle_get_state(int fd) {
    char resp[512];
    snprintf(resp, sizeof(resp),
        "{\"battery\":%d,\"ios_version\":\"%s\",\"model\":\"%s\",\"is_locked\":%s}",
        cfg.battery, cfg.ios_version, cfg.model,
        cfg.is_locked ? "true" : "false");
    send_line(fd, resp);
}

/* Returns 1 if connection should be dropped, 0 otherwise */
static int handle_run_stage(int fd, const char *attack_id, int stage_idx) {
    (void)attack_id; /* simulator doesn't validate attack_id */

    if (cfg.fail_stage >= 0 && stage_idx == cfg.fail_stage) {
        send_line(fd, "{\"status\":\"FAIL\",\"reason\":\"scripted failure\"}");
        return 0;
    }

    send_line(fd, "{\"status\":\"SUCCESS\"}");

    if (cfg.drop_after_stage >= 0 && stage_idx == cfg.drop_after_stage) {
        return 1; /* signal: drop connection */
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/* LIST command                                                         */
/* ------------------------------------------------------------------ */

/* Escape a string for JSON (handles backslash and double-quote only). */
static void json_escape(const char *in, char *out, size_t outlen) {
    size_t i = 0, j = 0;
    while (in[i] && j + 4 < outlen) {
        if (in[i] == '\\' || in[i] == '"') out[j++] = '\\';
        out[j++] = in[i++];
    }
    out[j] = '\0';
}

static void handle_list_real(int fd, const char *path) {
    /* Build full path under sim_files root */
    char full[MAX_PATH];
    snprintf(full, sizeof(full), "%s%s", cfg.sim_files, path);

    DIR *dp = opendir(full);
    char resp[MAX_LINE];
    if (!dp) {
        snprintf(resp, sizeof(resp), "{\"files\":[]}");
        send_line(fd, resp);
        return;
    }

    /* Collect entries */
    struct dirent *ent;
    char names[64][256];
    int count = 0;
    while ((ent = readdir(dp)) != NULL && count < 64) {
        if (strcmp(ent->d_name, ".") == 0 || strcmp(ent->d_name, "..") == 0)
            continue;
        strncpy(names[count], ent->d_name, 255);
        names[count][255] = '\0';
        count++;
    }
    closedir(dp);

    /* Build JSON array */
    char arr[MAX_LINE] = "{\"files\":[";
    for (int i = 0; i < count; i++) {
        char escaped[512];
        json_escape(names[i], escaped, sizeof(escaped));
        if (i > 0) strncat(arr, ",", sizeof(arr) - strlen(arr) - 1);
        strncat(arr, "\"", sizeof(arr) - strlen(arr) - 1);
        strncat(arr, escaped, sizeof(arr) - strlen(arr) - 1);
        strncat(arr, "\"", sizeof(arr) - strlen(arr) - 1);
    }
    strncat(arr, "]}", sizeof(arr) - strlen(arr) - 1);
    send_line(fd, arr);
}

static void handle_list_fake(int fd, const char *path) {
    /* Collect immediate children under path from the fake_files table */
    char norm[MAX_PATH];
    strncpy(norm, path, sizeof(norm) - 1);
    norm[sizeof(norm)-1] = '\0';
    /* strip trailing slash except for root */
    size_t len = strlen(norm);
    if (len > 1 && norm[len-1] == '/') norm[len-1] = '\0';

    char arr[MAX_LINE] = "{\"files\":[";
    int first = 1;

    for (FakeFile *f = fake_files; f->path; f++) {
        /* Check if f->path is a direct child of norm */
        size_t nlen = strlen(norm);
        if (strncmp(f->path, norm, nlen) != 0) continue;
        const char *rest = f->path + nlen;
        if (strcmp(norm, "/") != 0) {
            if (*rest != '/') continue;
            rest++;
        } else {
            if (*rest == '/') rest++;
        }
        /* rest should have no '/' → direct child */
        if (strchr(rest, '/') != NULL) {
            /* deeper descendant — check if its immediate child dir is already added */
            char child[256];
            const char *slash = strchr(rest, '/');
            size_t clen = (size_t)(slash - rest);
            if (clen >= sizeof(child)) continue;
            strncpy(child, rest, clen);
            child[clen] = '\0';

            /* Check if already in output */
            char probe[300];
            snprintf(probe, sizeof(probe), "\"%s\"", child);
            if (strstr(arr, probe)) continue;

            if (!first) strncat(arr, ",", sizeof(arr) - strlen(arr) - 1);
            strncat(arr, "\"", sizeof(arr) - strlen(arr) - 1);
            strncat(arr, child, sizeof(arr) - strlen(arr) - 1);
            strncat(arr, "\"", sizeof(arr) - strlen(arr) - 1);
            first = 0;
        } else {
            /* direct file child */
            if (!first) strncat(arr, ",", sizeof(arr) - strlen(arr) - 1);
            strncat(arr, "\"", sizeof(arr) - strlen(arr) - 1);
            char escaped[512];
            json_escape(rest, escaped, sizeof(escaped));
            strncat(arr, escaped, sizeof(arr) - strlen(arr) - 1);
            strncat(arr, "\"", sizeof(arr) - strlen(arr) - 1);
            first = 0;
        }
    }
    strncat(arr, "]}", sizeof(arr) - strlen(arr) - 1);
    send_line(fd, arr);
}

static void handle_list(int fd, const char *path) {
    if (cfg.sim_files[0])
        handle_list_real(fd, path);
    else
        handle_list_fake(fd, path);
}

/* ------------------------------------------------------------------ */
/* READ command                                                         */
/* ------------------------------------------------------------------ */

static void handle_read_real(int fd, const char *path) {
    char full[MAX_PATH];
    snprintf(full, sizeof(full), "%s%s", cfg.sim_files, path);
    FILE *fp = fopen(full, "rb");
    if (!fp) {
        send_line(fd, "{\"size\":0}");
        return;
    }
    fseek(fp, 0, SEEK_END);
    long sz = ftell(fp);
    fseek(fp, 0, SEEK_SET);

    char hdr[64];
    snprintf(hdr, sizeof(hdr), "{\"size\":%ld}", sz);
    send_line(fd, hdr);

    char buf[4096];
    size_t n;
    while ((n = fread(buf, 1, sizeof(buf), fp)) > 0) {
        send_all(fd, buf, n);
    }
    fclose(fp);
}

static void handle_read_fake(int fd, const char *path) {
    for (FakeFile *f = fake_files; f->path; f++) {
        if (strcmp(f->path, path) == 0) {
            size_t sz = strlen(f->content);
            char hdr[64];
            snprintf(hdr, sizeof(hdr), "{\"size\":%zu}", sz);
            send_line(fd, hdr);
            send_all(fd, f->content, sz);
            return;
        }
    }
    send_line(fd, "{\"size\":0}");
}

static void handle_read(int fd, const char *path) {
    if (cfg.sim_files[0])
        handle_read_real(fd, path);
    else
        handle_read_fake(fd, path);
}

/* ------------------------------------------------------------------ */
/* Connection handler                                                   */
/* ------------------------------------------------------------------ */

static void handle_connection(int fd) {
    char line[MAX_LINE];
    for (;;) {
        int n = recv_line(fd, line, sizeof(line));
        if (n <= 0) break;

        /* Strip trailing \r\n */
        int len = (int)strlen(line);
        while (len > 0 && (line[len-1] == '\n' || line[len-1] == '\r'))
            line[--len] = '\0';

        if (strcmp(line, "GET_STATE") == 0) {
            handle_get_state(fd);

        } else if (strncmp(line, "RUN_STAGE ", 10) == 0) {
            char attack_id[128] = "";
            int stage_idx = 0;
            sscanf(line + 10, "%127s %d", attack_id, &stage_idx);
            int drop = handle_run_stage(fd, attack_id, stage_idx);
            if (drop) break;

        } else if (strncmp(line, "LIST ", 5) == 0) {
            handle_list(fd, line + 5);

        } else if (strncmp(line, "READ ", 5) == 0) {
            handle_read(fd, line + 5);

        } else if (strcmp(line, "QUIT") == 0) {
            break;

        } else {
            send_line(fd, "{\"error\":\"unknown command\"}");
        }
    }
    close(fd);
}

/* ------------------------------------------------------------------ */
/* Argument parsing                                                     */
/* ------------------------------------------------------------------ */

static void parse_args(int argc, char *argv[]) {
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--port") == 0 && i+1 < argc)
            cfg.port = atoi(argv[++i]);
        else if (strcmp(argv[i], "--model") == 0 && i+1 < argc)
            strncpy(cfg.model, argv[++i], sizeof(cfg.model)-1);
        else if (strcmp(argv[i], "--ios") == 0 && i+1 < argc)
            strncpy(cfg.ios_version, argv[++i], sizeof(cfg.ios_version)-1);
        else if (strcmp(argv[i], "--battery") == 0 && i+1 < argc)
            cfg.battery = atoi(argv[++i]);
        else if (strcmp(argv[i], "--locked") == 0 && i+1 < argc)
            cfg.is_locked = atoi(argv[++i]);
        else if (strcmp(argv[i], "--fail-stage") == 0 && i+1 < argc)
            cfg.fail_stage = atoi(argv[++i]);
        else if (strcmp(argv[i], "--drop-after-stage") == 0 && i+1 < argc)
            cfg.drop_after_stage = atoi(argv[++i]);
        else if (strcmp(argv[i], "--sim-files") == 0 && i+1 < argc)
            strncpy(cfg.sim_files, argv[++i], sizeof(cfg.sim_files)-1);
    }
}

/* ------------------------------------------------------------------ */
/* main                                                                 */
/* ------------------------------------------------------------------ */

int main(int argc, char *argv[]) {
    parse_args(argc, argv);

#ifdef _WIN32
    WSADATA wsa;
    WSAStartup(MAKEWORD(2,2), &wsa);
#endif

    int srv = socket(AF_INET, SOCK_STREAM, 0);
    if (srv < 0) { perror("socket"); return 1; }

    int opt = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, (const char *)&opt, sizeof(opt));

    struct sockaddr_in addr = {0};
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port        = htons((uint16_t)cfg.port);

    if (bind(srv, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind"); return 1;
    }
    if (listen(srv, BACKLOG) < 0) { perror("listen"); return 1; }

    fprintf(stderr,
        "simulator: model=%s ios=%s battery=%d%% locked=%d "
        "fail_stage=%d drop_after=%d port=%d\n",
        cfg.model, cfg.ios_version, cfg.battery, cfg.is_locked,
        cfg.fail_stage, cfg.drop_after_stage, cfg.port);
    fflush(stderr);

    for (;;) {
        struct sockaddr_in client_addr;
        socklen_t clen = sizeof(client_addr);
        int cfd = accept(srv, (struct sockaddr *)&client_addr, &clen);
        if (cfd < 0) {
            if (errno == EINTR) continue;
            perror("accept");
            break;
        }
        handle_connection(cfd);
    }

    close(srv);
    return 0;
}
