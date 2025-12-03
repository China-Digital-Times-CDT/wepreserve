import {
  DownOutlined,
  NumberOutlined,
  PlusOutlined,
  RightOutlined,
  UpOutlined,
} from "@ant-design/icons";
import { isNotUndefined, TreeMenuNode } from "@dendronhq/common-all";
import { createLogger } from "@dendronhq/common-frontend";
import { Typography } from "antd";
import _ from "lodash";
import dynamic from "next/dynamic";
import Link from "next/link";
import { DataNode } from "rc-tree/lib/interface";
import { useCallback, useMemo } from "react";
import { useCombinedSelector } from "../features";
import { DENDRON_STYLE_CONSTANTS } from "../styles/constants";
import { useDendronRouter } from "../utils/hooks";
import { NoteData } from "../utils/types";

const Menu = dynamic(() => import("./AntdMenuWrapper"), {
  ssr: false,
});

const SubMenu = dynamic(() => import("./AntdSubMenuWrapper"), {
  ssr: false,
});

const MenuItem = dynamic(() => import("./AntdMenuItemWrapper"), {
  ssr: false,
});

export default function DendronTreeMenu(
  props: Partial<NoteData> & {
    collapsed: boolean;
    setCollapsed: (collapsed: boolean) => void;
  }
) {
  const ide = useCombinedSelector((state) => state.ide);
  const tree = ide.tree;
  const logger = createLogger("DendronTreeMenu");
  const dendronRouter = useDendronRouter();
  const noteActiveId = _.isUndefined(dendronRouter.query.id)
    ? props.noteIndex?.id
    : dendronRouter.query.id;

  const { collapsed, setCollapsed } = props;

  const roots = useMemo(() => {
    if (!tree) return [];
    return treeMenuNode2DataNode({
      roots: tree.roots,
      showVaultName: false,
    });
  }, [tree]);

  const expandKeys = useMemo(() => {
    // Only expand top-level roots to avoid an over-expanded tree.
    return roots.map((n) => String(n.key));
  }, [roots]);

  // --- Methods
  const onSubMenuSelect = (noteId: string) => {
    logger.info({ ctx: "onSubMenuSelect", id: noteId });
    setCollapsed(true);
  };

  const onMenuItemClick = (noteId: string) => {
    logger.info({ ctx: "onMenuItemClick", id: noteId });
    setCollapsed(true);
  };

  if (!tree) {
    return null;
  }

  return noteActiveId ? (
    <MenuView
      {...props}
      roots={roots}
      expandKeys={expandKeys}
      onSubMenuSelect={onSubMenuSelect}
      onMenuItemClick={onMenuItemClick}
      collapsed={collapsed}
      activeNote={noteActiveId}
    />
  ) : (
    <></>
  );
}

function MenuView({
  roots,
  expandKeys,
  onSubMenuSelect,
  onMenuItemClick,
  collapsed,
  activeNote,
  noteIndex,
}: {
  roots: DataNode[];
  expandKeys: string[];
  onSubMenuSelect: (noteId: string) => void;
  onMenuItemClick: (noteId: string) => void;
  collapsed: boolean;
  activeNote: string;
} & Partial<NoteData>) {
  const ExpandIcon = useCallback(
    ({ isOpen }: { isOpen: boolean }) => {
      const UncollapsedIcon = isOpen ? UpOutlined : DownOutlined;
      const Icon = collapsed ? RightOutlined : UncollapsedIcon;
      return (
        <i data-expandedicon="true">
          <Icon
            style={{
              pointerEvents: "none", // only allow custom element to be gesture target
              margin: 0,
            }}
          />
        </i>
      );
    },
    [collapsed]
  );

  const createMenu = (menu: DataNode) => {
    if (menu.children && menu.children.length > 0) {
      return (
        // @ts-ignore
        <SubMenu
          // @ts-ignore
          icon={menu.icon}
          className={
            menu.key === activeNote ? "dendron-ant-menu-submenu-selected" : ""
          }
          key={menu.key}
          title={
            <MenuItemTitle
              menu={menu}
              noteIndex={noteIndex}
              onSubMenuSelect={onSubMenuSelect}
            />
          }
          onTitleClick={(event) => {
            const target = event.domEvent.target as HTMLElement;
            const isAnchor = target.nodeName === "A";
            // When not an anchor, keep menu expanded (all keys stay open by default)
            if (!isAnchor) return;
          }}
        >
          {menu.children.map((childMenu: DataNode) => {
            return createMenu(childMenu);
          })}
        </SubMenu>
      );
    }
    return (
      // @ts-ignore
      <MenuItem key={menu.key} icon={menu.icon}>
        <MenuItemTitle
          menu={menu}
          noteIndex={noteIndex}
          onSubMenuSelect={onSubMenuSelect}
        />
      </MenuItem>
    );
  };

  return (
    // @ts-ignore
    <Menu
      key={String(collapsed)}
      className="dendron-tree-menu"
      mode="inline"
      defaultOpenKeys={expandKeys}
      selectedKeys={[activeNote]}
      inlineIndent={DENDRON_STYLE_CONSTANTS.SIDER.INDENT}
      // @ts-ignore
      expandIcon={ExpandIcon}
      inlineCollapsed={collapsed}
      // results in gray box otherwise when nav bar is too short for display
      style={{ height: "100%" }}
      onClick={({ key }) => {
        onMenuItemClick(key);
      }}
    >
      {roots.map((menu) => {
        return createMenu(menu);
      })}
    </Menu>
  );
}

function MenuItemTitle(
  props: Partial<NoteData> & {
    menu: DataNode;
    onSubMenuSelect: (noteId: string) => void;
  }
) {
  const { getNoteUrl } = useDendronRouter();

  return (
    // @ts-ignore
    <Typography.Text ellipsis={{ tooltip: props.menu.title }}>
      <Link
        href={getNoteUrl(props.menu.key as string, {
          noteIndex: props.noteIndex,
        })}
        passHref
      >
        <a
          href={
            "dummy" /* a way to dodge eslint warning that conflicts with `next/link`. see https://github.com/vercel/next.js/discussions/32233#discussioncomment-1766768*/
          }
          onClick={() => {
            props.onSubMenuSelect(props.menu.key as string);
          }}
        >
          {/* @ts-ignore */}
          {props.menu.title}
        </a>
      </Link>
    </Typography.Text>
  );
}

function treeMenuNode2DataNode({
  roots,
  showVaultName,
}: {
  roots: TreeMenuNode[];
  showVaultName?: boolean;
}): DataNode[] {
  return roots
    .map((node: TreeMenuNode) => {
      let icon;
      if (node.icon === "numberOutlined") {
        icon = <NumberOutlined />;
      } else if (node.icon === "plusOutlined") {
        icon = <PlusOutlined />;
      }

      let title: any = node.title;
      if (showVaultName) title = `${title} (${node.vaultName})`;

      if (node.hasTitleNumberOutlined) {
        title = (
          <span>
            <NumberOutlined />
            {title}
          </span>
        );
      }

      return {
        key: node.key,
        title,
        icon,
        children: node.children
          ? treeMenuNode2DataNode({
              roots: node.children,
              showVaultName,
            })
          : [],
      };
    })
    .filter(isNotUndefined);
}
