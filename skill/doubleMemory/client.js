window.__ModuleLoader__.load({
  id: 'doublememory',
  factory(require) {
    const React = require('react')
    const h = React.createElement
    const NS = 'memory.settings'

    const en = {
      nav: 'Memory',
      title: 'Memory',
      intro: 'Persistent identity, dated notes, conversation archives, and image albums. Settings are saved to this profile.',
      tabGlobal: 'Global',
      tabSessions: 'Session overrides',
      globalTitle: 'Global defaults',
      globalHint: 'These values apply to every session unless a session override below changes them.',
      sessionTitle: 'Session overrides',
      sessionHint: 'An override applies only to the selected session. Empty fields inherit the global value.',
      rootMode: 'Memory root mode',
      rootModeGlobal: 'Global shared folder',
      rootModeWorkspace: 'Per-workspace .dsh-memory (QQ bot / isolated agents)',
      rootModeHint: 'Workspace mode creates an independent .dsh-memory folder inside each session\'s working directory, fully isolated from the global memory.',
      root: 'Memory folder',
      rootHint: 'Leave empty for ~/.dsh/memory. Relative session folders resolve against this folder.',
      autoCapture: 'Archive conversations',
      autoCaptureHint: 'Append user and assistant messages to session/YYYY-MM-DD.json.',
      captureAssistant: 'Include assistant replies',
      captureAssistantHint: 'Archive assistant messages as well as user messages.',
      captureSubagents: 'Include subagent sessions',
      captureSubagentsHint: 'Subagent sessions are skipped by default to keep the archive focused.',
      copyImages: 'Copy images into pic/image',
      copyImagesHint: 'Conversation images are copied and linked as <img src="pic/image/...">.',
      injectContext: 'Add memory to the system prompt',
      injectContextHint: 'Include soul.md, IDENTITY.md, and MEMORY.md in the model context.',
      maxContextChars: 'Prompt budget (characters)',
      maxContextCharsHint: 'A larger budget gives the model more memory but costs more tokens.',
      save: 'Save',
      saving: 'Saving…',
      saved: 'Saved',
      saveFailed: 'The deployment did not accept these values. Check the fields and try again.',
      readOnly: 'This deployment stores settings read-only.',
      unavailable: 'Memory settings are not available until the memory plugin is loaded.',
      loading: 'Loading memory settings…',
      session: 'Session',
      noOverrides: 'No session overrides yet',
      chooseSession: 'Choose a session…',
      sessionId: 'Session ID',
      sessionIdPlaceholder: 'session-…',
      add: 'Add',
      useCurrent: 'Use current session',
      remove: 'Remove override',
      enabled: 'Memory enabled',
      enabledHint: 'Turn off to stop context injection and automatic archiving for this session.',
      sessionRoot: 'Session memory folder',
      sessionRootHint: 'Empty inherits the global folder. A relative path resolves against the global folder.',
      note: 'Note',
      noteHint: 'A short note about why this session is different.',
      overrideExists: 'This session has an override.',
      overrideNew: 'This session has no saved override yet; saving will create one.',
      emptySession: 'Add a session ID to create an override.',
    }

    const zh = {
      nav: '记忆',
      title: '记忆',
      intro: '持久化身份、每日记忆、会话归档与图片相册。设置保存到当前配置。',
      tabGlobal: '全局',
      tabSessions: '会话覆盖（非全局）',
      globalTitle: '全局默认值',
      globalHint: '这些值应用于所有会话，除非下面的会话覆盖修改了它们。',
      sessionTitle: '会话级覆盖（非全局）',
      sessionHint: '覆盖只对选中的会话生效；留空的字段继承全局值。',
      rootMode: '记忆根目录模式',
      rootModeGlobal: '全局共享目录',
      rootModeWorkspace: '工作区独立目录（QQ机器人 / 隔离代理）',
      rootModeHint: '工作区模式会在每个会话的工作目录下创建独立的 .dsh-memory 目录，与全局记忆完全隔离。',
      root: '记忆文件夹',
      rootHint: '留空使用 ~/.dsh/memory。会话级相对路径会基于这个文件夹解析。',
      autoCapture: '自动归档会话',
      autoCaptureHint: '把用户和助手消息追加到 session/YYYY-MM-DD.json。',
      captureAssistant: '包含助手回复',
      captureAssistantHint: '除了用户消息，也归档助手消息。',
      captureSubagents: '包含子代理会话',
      captureSubagentsHint: '默认跳过子代理会话，让归档更聚焦。',
      copyImages: '把图片复制到 pic/image',
      copyImagesHint: '会话图片会被复制，并以 <img src="pic/image/..."> 的形式记录。',
      injectContext: '把记忆加入系统提示',
      injectContextHint: '把 soul.md、IDENTITY.md 和 MEMORY.md 注入模型上下文。',
      maxContextChars: '提示预算（字符）',
      maxContextCharsHint: '预算越大，模型能看到的记忆越多，但消耗的 token 也越多。',
      save: '保存',
      saving: '保存中…',
      saved: '已保存',
      saveFailed: '部署没有接受这些值。请检查字段后重试。',
      readOnly: '本部署的设置为只读。',
      unavailable: '记忆插件加载后才能配置。',
      loading: '正在加载记忆设置…',
      session: '会话',
      noOverrides: '还没有会话覆盖',
      chooseSession: '选择一个会话…',
      sessionId: '会话 ID',
      sessionIdPlaceholder: 'session-…',
      add: '添加',
      useCurrent: '当前会话',
      remove: '删除覆盖',
      enabled: '启用记忆',
      enabledHint: '关闭后，该会话不再注入记忆，也不再自动归档。',
      sessionRoot: '会话记忆文件夹',
      sessionRootHint: '留空继承全局文件夹。相对路径基于全局文件夹解析。',
      note: '备注',
      noteHint: '简单说明这个会话为什么需要不同配置。',
      overrideExists: '这个会话已有覆盖。',
      overrideNew: '这个会话还没有保存覆盖；保存后会创建。',
      emptySession: '输入会话 ID 来创建覆盖。',
    }

    const CSS = `
.dsh-memory-page{max-width:760px;display:flex;flex-direction:column;gap:14px;color:var(--dsw-alias-label-primary);font-family:inherit}
.dsh-memory-title{margin:0;font-size:18px;font-weight:600;line-height:26px}
.dsh-memory-intro{margin:0;color:var(--dsw-alias-label-secondary);font-size:13px;line-height:20px}
.dsh-memory-tabs{display:flex;align-items:flex-end;gap:20px;border-bottom:1px solid var(--dsw-alias-border-l2);margin-top:2px}
.dsh-memory-tab{appearance:none;border:0;background:transparent;color:var(--dsw-alias-label-secondary);font:inherit;font-size:13px;line-height:20px;padding:7px 1px 9px;cursor:pointer;position:relative}
.dsh-memory-tab[data-active=true]{color:var(--dsw-alias-label-primary)}
.dsh-memory-tab[data-active=true]:after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:2px;border-radius:2px 2px 0 0;background:var(--dsw-alias-label-primary)}
.dsh-memory-tab:focus-visible{outline:2px solid var(--dsw-alias-brand-primary);outline-offset:2px;border-radius:3px}
.dsh-memory-card{display:flex;flex-direction:column;gap:14px;padding:18px;border:1px solid var(--dsw-alias-border-l1);border-radius:12px;background:var(--dsw-alias-bg-layer-1)}
.dsh-memory-card-head{display:flex;flex-direction:column;gap:4px}
.dsh-memory-card-title{margin:0;font-size:15px;font-weight:600;line-height:22px}
.dsh-memory-card-hint{margin:0;color:var(--dsw-alias-label-secondary);font-size:12px;line-height:18px}
.dsh-memory-field{display:flex;flex-direction:column;gap:6px}
.dsh-memory-label{font-size:13px;font-weight:500;line-height:18px;color:var(--dsw-alias-label-primary)}
.dsh-memory-hint{font-size:12px;line-height:18px;color:var(--dsw-alias-label-secondary)}
.dsh-memory-input,.dsh-memory-select,.dsh-memory-textarea{box-sizing:border-box;width:100%;border:1px solid var(--dsw-alias-border-l2);border-radius:8px;background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-primary);font:inherit;font-size:13px;line-height:20px;padding:8px 10px}
.dsh-memory-textarea{min-height:66px;resize:vertical}
.dsh-memory-input:focus,.dsh-memory-select:focus,.dsh-memory-textarea:focus{outline:2px solid var(--dsw-alias-brand-primary);outline-offset:1px}
.dsh-memory-input:disabled,.dsh-memory-select:disabled,.dsh-memory-textarea:disabled{opacity:.55;cursor:not-allowed}
.dsh-memory-switch{display:flex;align-items:flex-start;gap:10px;cursor:pointer}
.dsh-memory-switch input{margin:2px 0 0;accent-color:var(--dsw-alias-brand-primary);width:15px;height:15px;flex:none}
.dsh-memory-switch-copy{display:flex;flex-direction:column;gap:2px;min-width:0}
.dsh-memory-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.dsh-memory-row .dsh-memory-select{flex:1;min-width:190px}
.dsh-memory-row .dsh-memory-input{flex:1;min-width:190px}
.dsh-memory-button{appearance:none;border:1px solid transparent;border-radius:8px;padding:7px 14px;font:inherit;font-size:13px;line-height:20px;cursor:pointer;background:var(--dsw-alias-brand-primary);color:var(--dsw-alias-bg-layer-1)}
.dsh-memory-button:hover{filter:brightness(1.06)}
.dsh-memory-button:focus-visible{outline:2px solid var(--dsw-alias-brand-primary);outline-offset:2px}
.dsh-memory-button:disabled{opacity:.5;cursor:not-allowed}
.dsh-memory-button.secondary{background:transparent;border-color:var(--dsw-alias-border-l2);color:var(--dsw-alias-label-primary)}
.dsh-memory-button.danger{background:transparent;border-color:var(--dsw-alias-state-error-primary);color:var(--dsw-alias-state-error-primary)}
.dsh-memory-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.dsh-memory-status{min-height:18px;font-size:12px;line-height:18px;color:var(--dsw-alias-label-secondary)}
.dsh-memory-status.success{color:var(--dsw-alias-state-success-primary)}
.dsh-memory-status.error{color:var(--dsw-alias-state-error-primary)}
.dsh-memory-empty{color:var(--dsw-alias-label-secondary);font-size:13px;line-height:20px}
`

    function readGlobal(value) {
      return {
        root: typeof value?.root === 'string' ? value.root : '',
        rootMode: value?.rootMode === 'workspace' ? 'workspace' : 'global',
        autoCapture: value?.autoCapture !== false,
        captureAssistant: value?.captureAssistant !== false,
        captureSubagents: value?.captureSubagents === true,
        copyImages: value?.copyImages !== false,
        injectContext: value?.injectContext !== false,
        maxContextChars:
          typeof value?.maxContextChars === 'number' && Number.isFinite(value.maxContextChars)
            ? String(value.maxContextChars)
            : '4000',
      }
    }

    function readSession(value, fallback) {
      const base = fallback || readGlobal(undefined)
      return {
        enabled: value?.enabled !== false,
        autoCapture: typeof value?.autoCapture === 'boolean' ? value.autoCapture : base.autoCapture,
        captureAssistant: typeof value?.captureAssistant === 'boolean' ? value.captureAssistant : base.captureAssistant,
        injectContext: typeof value?.injectContext === 'boolean' ? value.injectContext : base.injectContext,
        root: typeof value?.root === 'string' ? value.root : '',
        note: typeof value?.note === 'string' ? value.note : '',
      }
    }

    function shortId(value) {
      const text = String(value)
      return text.length > 22 ? `${text.slice(0, 10)}…${text.slice(-8)}` : text
    }

    function Field({ label, hint, children }) {
      return h(
        'label',
        { className: 'dsh-memory-field' },
        h('span', { className: 'dsh-memory-label' }, label),
        children,
        hint ? h('span', { className: 'dsh-memory-hint' }, hint) : null,
      )
    }

    function Switch({ label, hint, checked, onChange, disabled }) {
      return h(
        'label',
        { className: 'dsh-memory-switch' },
        h('input', { type: 'checkbox', checked: !!checked, onChange: (event) => onChange(event.target.checked), disabled }),
        h(
          'span',
          { className: 'dsh-memory-switch-copy' },
          h('span', { className: 'dsh-memory-label' }, label),
          hint ? h('span', { className: 'dsh-memory-hint' }, hint) : null,
        ),
      )
    }

    function Tab({ active, children, onClick }) {
      return h(
        'button',
        {
          type: 'button',
          role: 'tab',
          className: 'dsh-memory-tab',
          'data-active': active ? 'true' : undefined,
          'aria-selected': active,
          onClick,
        },
        children,
      )
    }

    function MemorySettings(props) {
      const { t } = props
      const state = props.useMemorySettings((snapshot) => snapshot)
      const [tab, setTab] = React.useState('global')
      const [draft, setDraft] = React.useState(() => readGlobal(state?.value))
      const [selected, setSelected] = React.useState('')
      const [sessionDraft, setSessionDraft] = React.useState(() => readSession(null, readGlobal(undefined)))
      const [newId, setNewId] = React.useState('')
      const [status, setStatus] = React.useState('idle')
      const revision = state?.revision
      const sessions = React.useMemo(() => Object.keys(state?.value?.sessions || {}).sort(), [state?.value, revision])
      const activeId = selected || sessions[0] || ''
      const isExisting = sessions.includes(activeId)
      const sessionList = props.useSessions((snapshot) => snapshot)
      const currentSessionId = React.useMemo(() => {
        const byId = sessionList?.byId || {}
        const retained = Object.values(byId).find((session) => (session?.retainedBy?.mainView ?? 0) > 0)
        return retained?.id ? String(retained.id) : ''
      }, [sessionList])

      React.useEffect(() => {
        if (state?.status === 'ready') setDraft(readGlobal(state.value))
      }, [revision, state?.status])

      React.useEffect(() => {
        if (!selected && sessions.length > 0) setSelected(sessions[0])
      }, [selected, sessions.length])

      React.useEffect(() => {
        setSessionDraft(readSession(state?.value?.sessions?.[activeId], draft))
      }, [activeId, revision, state?.status])

      const writable = state?.writable !== false
      const ready = state?.status === 'ready'

      function change(key, value) {
        setStatus('idle')
        setDraft((current) => ({ ...current, [key]: value }))
      }

      function changeSession(key, value) {
        setStatus('idle')
        setSessionDraft((current) => ({ ...current, [key]: value }))
      }

      async function saveGlobal() {
        setStatus('saving')
        const max = Number.parseInt(draft.maxContextChars, 10)
        const ops = [
          { op: 'set', path: ['root'], value: String(draft.root || '').trim() },
          { op: 'set', path: ['rootMode'], value: draft.rootMode === 'workspace' ? 'workspace' : 'global' },
          { op: 'set', path: ['autoCapture'], value: !!draft.autoCapture },
          { op: 'set', path: ['captureAssistant'], value: !!draft.captureAssistant },
          { op: 'set', path: ['captureSubagents'], value: !!draft.captureSubagents },
          { op: 'set', path: ['copyImages'], value: !!draft.copyImages },
          { op: 'set', path: ['injectContext'], value: !!draft.injectContext },
          { op: 'set', path: ['maxContextChars'], value: Number.isFinite(max) ? max : 4000 },
        ]
        try {
          const ok = await props.saveGlobal(ops)
          setStatus(ok ? 'saved' : 'error')
        } catch {
          setStatus('error')
        }
      }

      async function saveSession() {
        if (!activeId) return
        setStatus('saving')
        try {
          const ok = await props.saveSession(activeId, {
            enabled: !!sessionDraft.enabled,
            autoCapture: !!sessionDraft.autoCapture,
            captureAssistant: !!sessionDraft.captureAssistant,
            injectContext: !!sessionDraft.injectContext,
            root: String(sessionDraft.root || '').trim(),
            note: String(sessionDraft.note || ''),
          })
          setStatus(ok ? 'saved' : 'error')
        } catch {
          setStatus('error')
        }
      }

      async function removeSession() {
        if (!activeId) return
        setStatus('saving')
        try {
          const ok = await props.removeSession(activeId)
          if (ok) {
            setSelected(sessions.filter((id) => id !== activeId)[0] || '')
            setStatus('saved')
          } else setStatus('error')
        } catch {
          setStatus('error')
        }
      }

      function addSession() {
        const id = newId.trim()
        if (!id) return
        setSelected(id)
        setNewId('')
        setStatus('idle')
      }

      function useCurrentSession() {
        if (!currentSessionId) return
        setSelected(currentSessionId)
        setNewId('')
        setStatus('idle')
      }

      const statusText =
        status === 'saved'
          ? t('saved')
          : status === 'saving'
            ? t('saving')
            : status === 'error'
              ? t('saveFailed')
              : ''

      const globalView = h(
        'section',
        { className: 'dsh-memory-card' },
        h(
          'div',
          { className: 'dsh-memory-card-head' },
          h('h3', { className: 'dsh-memory-card-title' }, t('globalTitle')),
          h('p', { className: 'dsh-memory-card-hint' }, t('globalHint')),
        ),
        h(
          Field,
          { label: t('root'), hint: t('rootHint') },
          h('input', {
            className: 'dsh-memory-input',
            type: 'text',
            value: draft.root,
            placeholder: '~/.dsh/memory',
            disabled: !writable || draft.rootMode === 'workspace',
            onChange: (event) => change('root', event.target.value),
          }),
        ),
        h(
          Field,
          { label: t('rootMode'), hint: t('rootModeHint') },
          h(
            'select',
            {
              className: 'dsh-memory-select',
              value: draft.rootMode,
              disabled: !writable,
              onChange: (event) => change('rootMode', event.target.value),
            },
            h('option', { value: 'global' }, t('rootModeGlobal')),
            h('option', { value: 'workspace' }, t('rootModeWorkspace')),
          ),
        ),
        h(Switch, {
          label: t('autoCapture'),
          hint: t('autoCaptureHint'),
          checked: draft.autoCapture,
          disabled: !writable,
          onChange: (value) => change('autoCapture', value),
        }),
        h(Switch, {
          label: t('captureAssistant'),
          hint: t('captureAssistantHint'),
          checked: draft.captureAssistant,
          disabled: !writable,
          onChange: (value) => change('captureAssistant', value),
        }),
        h(Switch, {
          label: t('captureSubagents'),
          hint: t('captureSubagentsHint'),
          checked: draft.captureSubagents,
          disabled: !writable,
          onChange: (value) => change('captureSubagents', value),
        }),
        h(Switch, {
          label: t('copyImages'),
          hint: t('copyImagesHint'),
          checked: draft.copyImages,
          disabled: !writable,
          onChange: (value) => change('copyImages', value),
        }),
        h(Switch, {
          label: t('injectContext'),
          hint: t('injectContextHint'),
          checked: draft.injectContext,
          disabled: !writable,
          onChange: (value) => change('injectContext', value),
        }),
        h(
          Field,
          { label: t('maxContextChars'), hint: t('maxContextCharsHint') },
          h('input', {
            className: 'dsh-memory-input',
            type: 'number',
            min: 500,
            max: 50000,
            step: 1,
            value: draft.maxContextChars,
            disabled: !writable,
            onChange: (event) => change('maxContextChars', event.target.value),
          }),
        ),
        h(
          'div',
          { className: 'dsh-memory-actions' },
          h(
            'button',
            { type: 'button', className: 'dsh-memory-button', disabled: !writable || status === 'saving', onClick: saveGlobal },
            status === 'saving' ? t('saving') : t('save'),
          ),
        ),
      )

      const sessionView = h(
        'section',
        { className: 'dsh-memory-card' },
        h(
          'div',
          { className: 'dsh-memory-card-head' },
          h('h3', { className: 'dsh-memory-card-title' }, t('sessionTitle')),
          h('p', { className: 'dsh-memory-card-hint' }, t('sessionHint')),
        ),
        h(
          'div',
          { className: 'dsh-memory-row' },
          h(
            'select',
            {
              className: 'dsh-memory-select',
              value: activeId,
              disabled: !writable || sessions.length === 0,
              onChange: (event) => {
                setSelected(event.target.value)
                setStatus('idle')
              },
            },
            sessions.length === 0
              ? h('option', { value: '' }, t('noOverrides'))
              : sessions.map((id) => h('option', { value: id, key: id }, shortId(id))),
            activeId && !isExisting ? h('option', { value: activeId, key: activeId }, shortId(activeId)) : null,
          ),
          h(
            'button',
            {
              type: 'button',
              className: 'dsh-memory-button danger',
              disabled: !writable || !activeId || !isExisting || status === 'saving',
              onClick: removeSession,
            },
            t('remove'),
          ),
        ),
        h(
          'div',
          { className: 'dsh-memory-row' },
          h('input', {
            className: 'dsh-memory-input',
            type: 'text',
            value: newId,
            placeholder: t('sessionIdPlaceholder'),
            'aria-label': t('sessionId'),
            disabled: !writable,
            onChange: (event) => setNewId(event.target.value),
            onKeyDown: (event) => {
              if (event.key === 'Enter') addSession()
            },
          }),
          h(
            'button',
            { type: 'button', className: 'dsh-memory-button secondary', disabled: !writable || !newId.trim(), onClick: addSession },
            t('add'),
          ),
          currentSessionId
            ? h(
                'button',
                { type: 'button', className: 'dsh-memory-button secondary', disabled: !writable, onClick: useCurrentSession },
                t('useCurrent'),
              )
            : null,
        ),
        activeId
          ? h(
              'p',
              { className: 'dsh-memory-hint' },
              isExisting ? t('overrideExists') : t('overrideNew'),
            )
          : h('p', { className: 'dsh-memory-empty' }, t('emptySession')),
        activeId
          ? h(
              React.Fragment,
              null,
              h(Switch, {
                label: t('enabled'),
                hint: t('enabledHint'),
                checked: sessionDraft.enabled,
                disabled: !writable,
                onChange: (value) => changeSession('enabled', value),
              }),
              h(Switch, {
                label: t('autoCapture'),
                hint: t('autoCaptureHint'),
                checked: sessionDraft.autoCapture,
                disabled: !writable,
                onChange: (value) => changeSession('autoCapture', value),
              }),
              h(Switch, {
                label: t('captureAssistant'),
                hint: t('captureAssistantHint'),
                checked: sessionDraft.captureAssistant,
                disabled: !writable,
                onChange: (value) => changeSession('captureAssistant', value),
              }),
              h(Switch, {
                label: t('injectContext'),
                hint: t('injectContextHint'),
                checked: sessionDraft.injectContext,
                disabled: !writable,
                onChange: (value) => changeSession('injectContext', value),
              }),
              h(
                Field,
                { label: t('sessionRoot'), hint: t('sessionRootHint') },
                h('input', {
                  className: 'dsh-memory-input',
                  type: 'text',
                  value: sessionDraft.root,
                  placeholder: t('rootHint'),
                  disabled: !writable,
                  onChange: (event) => changeSession('root', event.target.value),
                }),
              ),
              h(
                Field,
                { label: t('note'), hint: t('noteHint') },
                h('textarea', {
                  className: 'dsh-memory-textarea',
                  value: sessionDraft.note,
                  disabled: !writable,
                  onChange: (event) => changeSession('note', event.target.value),
                }),
              ),
              h(
                'div',
                { className: 'dsh-memory-actions' },
                h(
                  'button',
                  { type: 'button', className: 'dsh-memory-button', disabled: !writable || status === 'saving', onClick: saveSession },
                  status === 'saving' ? t('saving') : t('save'),
                ),
              ),
            )
          : null,
      )

      return h(
        'div',
        { className: 'dsh-memory-page' },
        h('h2', { className: 'dsh-memory-title' }, t('title')),
        h('p', { className: 'dsh-memory-intro' }, t('intro')),
        h(
          'div',
          { className: 'dsh-memory-tabs', role: 'tablist' },
          h(Tab, { active: tab === 'global', onClick: () => setTab('global') }, t('tabGlobal')),
          h(Tab, { active: tab === 'sessions', onClick: () => setTab('sessions') }, t('tabSessions')),
        ),
        ready
          ? tab === 'global'
            ? globalView
            : sessionView
          : h('p', { className: 'dsh-memory-empty' }, state?.status === 'unavailable' ? t('unavailable') : t('loading')),
        !writable ? h('p', { className: 'dsh-memory-hint' }, t('readOnly')) : null,
        h(
          'div',
          { className: `dsh-memory-status ${status === 'saved' ? 'success' : status === 'error' ? 'error' : ''}`.trim(), role: 'status' },
          statusText,
        ),
      )
    }

    return {
      inject: ['slots', 'locale'],
      apply(ctx) {
        const t = ctx.locale.bind(NS)
        ctx.effect(() => ctx.locale.register(NS, { en, zh }), 'memory: dictionaries')
        ctx.effect(() => {
          const style = document.createElement('style')
          style.dataset.plugin = 'doublememory'
          style.textContent = CSS
          document.head.appendChild(style)
          return () => style.remove()
        }, 'memory: styles')
        ctx.inject(['configForms'], (sub) => {
          sub.effect(
            () =>
              sub.configForms.whileServed(['doublememory'], () => {
                const form = sub.configForms.get('doublememory')
                const hook = {
                  getSnapshot: () => form.getSnapshot(),
                  subscribe: (listener) => form.subscribe(listener),
                }
                return sub.slots.inject('settings.section', () =>
                  sub.slots.register(
                    {
                      name: 'settings.section',
                      id: 'doublememory',
                      order: 18,
                      label: () => t('nav'),
                      locale: NS,
                      inject: () => ({
                        hooks: { memorySettings: hook },
                        saveGlobal: (ops) => form.mutate(ops),
                        saveSession: (sessionId, value) => {
                          const current = form.getSnapshot().value?.sessions
                          const sessions = current && typeof current === 'object' ? current : {}
                          return form.set('sessions', { ...sessions, [sessionId]: value })
                        },
                        removeSession: (sessionId) => {
                          const current = form.getSnapshot().value?.sessions
                          const sessions = current && typeof current === 'object' ? current : {}
                          const next = { ...sessions }
                          delete next[sessionId]
                          return form.set('sessions', next)
                        },
                      }),
                    },
                    MemorySettings,
                  ),
                )
              }),
            'memory: settings page',
          )
        })
      },
    }
  },
})
