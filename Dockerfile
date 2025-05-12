FROM ghcr.io/ad-sdl/madsci:latest

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
    pip install -e ./brooks_xpeel_module

CMD ["python", "brooks_xpeel_module/src/peeler_rest_node.py"]

#########################################
