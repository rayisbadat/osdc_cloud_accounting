from repquota import RepQuota

g = RepQuota()
g.load_quotas()
g.print_du()
g.write_to_db()
