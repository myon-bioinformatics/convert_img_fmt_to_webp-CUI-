FROM python:3.10.7-buster

ARG src=/src

WORKDIR $src

COPY . .

RUN pip install -U pip && \
    pip install --no-cache-dir -r requirements.txt

VOLUME $src

CMD ["python", "./src/convert_img_fmt_to_webp(CUI).py"]

#How to Try to Execute Commands(Basic)
#1: docker build ./ -t convert_img_fmt_to_webp_cui
#2: docker images
#3: docker run --name convert_img_fmt_to_webp_docker -it convert_img_fmt_to_webp_cui:latest
#  [info](Successed: Convert image files to webp files in img_folder AND print(All Completed!)
#4 docker ps -a
#5 docker inspect convert_img_fmt_to_webp_docker
#  [info]Notes yourself "Mounts"["Source"]. For example, "/var/lib/docker/volumes/~#abcd/_data
#6 docker container prune
#Option sudo sh -c "cd /var/lib/docker/volumes/~#abcd_data; ls -lsa"