FROM ghcr.io/ad-sdl/madsci:v0.8.0

LABEL org.opencontainers.image.source=https://github.com/AD-SDL/brooks_xpeel_module
LABEL org.opencontainers.image.description="Drivers and REST API's for the Brooks Peeler"
LABEL org.opencontainers.image.licenses=MIT

#########################################
# Module specific logic goes below here #
#########################################

RUN mkdir -p brooks_xpeel_module

COPY ./src brooks_xpeel_module/src
COPY ./README.md brooks_xpeel_module/README.md
COPY ./pyproject.toml brooks_xpeel_module/pyproject.toml

RUN --mount=type=cache,target=/root/.cache \
    uv pip install --python ${MADSCI_VENV}/bin/python -e ./brooks_xpeel_module

# Cross-distro serial access:
#   Ubuntu hosts: dialout = GID 20 (matches container's built-in `dialout` group).
#   Fedora hosts: dialout = GID 18 (added below as `dialout_fedora`).
# Baking both into the image means /dev/ttyUSB* works without compose-side
# `group_add` (which gets stripped by the madsci entrypoint's userdel/useradd).
RUN usermod -aG dialout madsci && \
    groupadd -g 18 dialout_fedora && \
    usermod -aG dialout_fedora madsci

CMD ["python", "brooks_xpeel_module/src/peeler_rest_node.py"]

#########################################
