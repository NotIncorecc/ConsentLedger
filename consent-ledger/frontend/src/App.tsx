import React from 'react'
import { NetworkId, WalletId, WalletManager, WalletProvider } from '@txnlab/use-wallet-react'
import { ZKConsentFlow } from './components/ZKConsentFlow'
import { ActiveConsents } from './components/ActiveConsents'
import { OrgConsents } from './components/OrgConsents'
import { OrgFormBuilder } from './components/OrgFormBuilder'
import { RegulatorView } from './components/RegulatorView'
import { Header } from './components/Header'
import { RolePicker } from './components/RolePicker'

const walletManager = new WalletManager({
  wallets: [WalletId.PERA],
  defaultNetwork: NetworkId.TESTNET,
})

export type Role = 'user' | 'org' | 'regulator'
export type UserView = 'grant' | 'consents'
export type OrgView = 'request' | 'granted' | 'forms'

function App() {
  // Auto-select 'user' role when a shared form URL is opened
  const hasFormParam = new URLSearchParams(window.location.search).has('form')
  const [role, setRole] = React.useState<Role | null>(hasFormParam ? 'user' : null)
  const [userView, setUserView] = React.useState<UserView>('grant')
  const [orgView, setOrgView] = React.useState<OrgView>('request')

  return (
    <WalletProvider manager={walletManager}>
      <div className="min-h-screen bg-gray-50 text-gray-900">
        {!role ? (
          <RolePicker onSelect={setRole} />
        ) : (
          <>
            <Header
              role={role}
              userView={userView}
              orgView={orgView}
              onUserViewChange={setUserView}
              onOrgViewChange={setOrgView}
              onRoleChange={() => setRole(null)}
            />
            <main className="max-w-2xl mx-auto px-4 py-8">
              {role === 'user' && userView === 'grant' && <ZKConsentFlow />}
              {role === 'user' && userView === 'consents' && <ActiveConsents />}
              {role === 'org' && orgView !== 'forms' && <OrgConsents view={orgView as 'request' | 'granted'} />}
              {role === 'org' && orgView === 'forms' && <OrgFormBuilder />}
              {role === 'regulator' && <RegulatorView />}
            </main>
          </>
        )}
      </div>
    </WalletProvider>
  )
}

export default App
