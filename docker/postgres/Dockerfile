FROM golang:1.26.10-alpine@sha256:a2012b4a1d1f9f7e9f44e0d39b805a901e856b1dd80b4e6ee4338db547050308 AS gosu-builder

ARG GOSU_COMMIT=29b939aa5bd4dc588af765b8248f6e39150d2565
ARG GOSU_SOURCE_SHA256=2b70da8a5480fafedc16bb1fc91b572f064d03df736cbd91a616af2f1b66ab51

RUN set -eux; \
    wget -O /tmp/gosu.tar.gz \
        "https://codeload.github.com/tianon/gosu/tar.gz/${GOSU_COMMIT}"; \
    echo "${GOSU_SOURCE_SHA256}  /tmp/gosu.tar.gz" | sha256sum -c -; \
    mkdir /src; \
    tar -xzf /tmp/gosu.tar.gz -C /src --strip-components=1; \
    cd /src; \
    test "$(awk -F\" '/const Version/ { print $2 }' version.go)" = "1.20"; \
    CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o /out/gosu .; \
    /out/gosu --version; \
    go version -m /out/gosu

FROM postgres:16.15-alpine@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab

# The upstream image contains gosu built with a vulnerable Go standard
# library. Keep PostgreSQL unchanged and replace only that privilege-drop
# helper with the pinned gosu source built by the patched Go toolchain above.
COPY --from=gosu-builder /out/gosu /usr/local/bin/gosu

RUN set -eux; \
    gosu --version; \
    gosu nobody true
