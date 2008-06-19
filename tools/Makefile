#
# This makefile handles various developer tasks, such as creating distribution
# packages  It is not particularly useful to end users.
#

TNAME=pyicq-t
EXTENSIONS=".tar.gz .rpm .deb"

all:
	@echo "This makefile is primarily for use by the author for creating"
	@echo "distributions and such.  It serves no purpose to the end user."
	@echo ""
	@echo "Available commands are:"
	@echo "srcdist   create a source distribution of the current version"
	@echo "rpmdist   create a rpm distribution of the current version"
	@echo "debdist   create a debian distribution of the current version"
	@echo "md5sums   determine md5 checksums of all distributions of the current version"
	@echo "dists     try to create all available distributions of the current version"
	@echo "testinst  create a test install directory based off local source tree"

dists: srcdist rpmdist debdist md5sums

srcdist:
	@ver=`cat src/legacy/glue.py | grep 'version =' | cut -f2 -d'"' | cut -f1 -d'"'`; \
	files=`svn list -R`; \
	rm -rf /tmp/$(TNAME)-$${ver}; \
	rm -f /tmp/$(TNAME)-$${ver}.tar.gz; \
	mkdir /tmp/$(TNAME)-$${ver}; \
	tar --no-recursion -cf - $${files} | ( cd /tmp/$(TNAME)-$${ver}; tar -xf - ); \
	mkdir -p /tmp/$(TNAME)-$${ver}/src/twistfix; \
	cd src/twistfix; \
	files=`svn list -R`; \
	tar --no-recursion -cf - $${files} | ( cd /tmp/$(TNAME)-$${ver}/src/twistfix; tar -xf - ); \
	cd /tmp; \
	tar --owner=nobody --group=nobody -cvzf $(TNAME)-$${ver}.tar.gz $(TNAME)-$${ver}; \
	ls -l $(TNAME)-$${ver}.tar.gz

rpmdist:
	@echo "Not supported yet."

debdist:
	@echo "Not supported yet."

md5sums:
	@ver=`cat src/legacy/glue.py | grep 'version =' | cut -f2 -d'"' | cut -f1 -d'"'`; \
	cd /tmp; \
	for E in `echo $(EXTENSIONS)`; do if [ -r "$(TNAME)-$${ver}$${E}" ]; then md5sum $(TNAME)-$${ver}$$E; else echo ".........Does not exist.........  $(TNAME)-$${ver}$$E"; fi; done

testinst:
	@files=`svn list -R`; \
	rm -rf ../$(TNAME)-test; \
	mkdir ../$(TNAME)-test; \
	tar --no-recursion -cf - $${files} | ( cd ../$(TNAME)-test; tar -xvf - );
