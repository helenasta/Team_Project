FROM ghcr.io/quarto-dev/quarto-full:latest

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    LANG=C.UTF-8

# Extra tools for this repo
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    make \
    gpg \
    python3 \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | gpg --dearmor -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

# Pin TinyTeX / tlmgr to a specific CTAN mirror and install the LaTeX packages
# needed by the paper template. Then verify that the required style files exist.
RUN tlmgr option repository https://ftp.fau.de/ctan/systems/texlive/tlnet \
    && tlmgr update --self \
    && tlmgr install \
    adjustbox \
    beamer \
    booktabs \
    caption \
    csquotes \
    endfloat \
    footmisc \
    geometry \
    latexmk \
    setspace \
    threeparttable \
    && test -n "$(kpsewhich adjustbox.sty)" \
    && test -n "$(kpsewhich beamer.cls)" \
    && test -n "$(kpsewhich booktabs.sty)" \
    && test -n "$(kpsewhich caption.sty)" \
    && test -n "$(kpsewhich csquotes.sty)" \
    && test -n "$(kpsewhich endfloat.sty)" \
    && test -n "$(kpsewhich footmisc.sty)" \
    && test -n "$(kpsewhich geometry.sty)" \
    && test -n "$(kpsewhich setspace.sty)" \
    && test -n "$(kpsewhich threeparttable.sty)"

# uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -sf /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /workspaces

CMD ["/bin/sh"]