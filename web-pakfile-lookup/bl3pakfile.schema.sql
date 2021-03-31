drop table if exists o2f;
drop table if exists object;
drop table if exists pakfile;
drop table if exists patch;

create table patch (
    pid int not null auto_increment,
    dirname varchar(100) not null,
    released date not null,
    description varchar(255) not null,
    primary key (pid),
    unique index (dirname)
) engine=innodb;

create table pakfile (
    fid int not null auto_increment,
    pid int not null,
    filename varchar(100) not null,
    mountpoint varchar(125) not null,
    ordernum int not null,
    primary key (fid),
    unique index (filename),
    constraint fk_pakfile_patch foreign key (pid) references patch (pid)
) engine=innodb;

create table object (
    oid int not null auto_increment,
    filename_base varchar(125) not null,
    filename_full varchar(255) not null,
    primary key (oid),
    index idx_base (filename_base),
    unique index idx_full (filename_full)
) engine=innodb;

create table o2f (
    oid int not null,
    fid int not null,
    primary key (oid, fid),
    constraint fk_o2f_object foreign key (oid) references object (oid),
    constraint fk_o2f_pakfile foreign key (fid) references pakfile (fid)
) engine=innodb;

