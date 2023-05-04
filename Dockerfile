FROM archlinux:latest
RUN	 pacman -Syy

# Install python and fortran
RUN	 pacman -S --noconfirm python
RUN	 pacman -S --noconfirm python-pip
RUN	 pacman -S --noconfirm gcc-fortran

# File sharing
COPY build.py /
COPY simulation.py /


# External packages
RUN python -m pip install numpy
RUN python -m pip install mfpymake
RUN python -m pip install flopy 
RUN python -m pip install https://github.com/pygsflow/pygsflow/zipball/develop 
RUN python -m pip install umbridge 

# COPY requirements.txt
# RUN python -m pip install -r requirements.txt

RUN python build.py
CMD python simulation.py
