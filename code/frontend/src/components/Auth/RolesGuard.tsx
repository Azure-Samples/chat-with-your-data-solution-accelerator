import { useState, useEffect } from 'react';
import { useMsal, MsalAuthenticationTemplate } from '@azure/msal-react';
import { InteractionType } from '@azure/msal-browser';
import { groupIds, loginRequest } from '../../authConfig';
import { SignOutButton } from './SignOutButton';
import styles from "./Auth.module.css";

export const RolesGuard = ({ ...props }) => {
  const { instance } = useMsal();
  const [isAuthorized, setIsAuthorized] = useState(false);

  const currentAccount = instance.getActiveAccount();

  const authRequest = {
    ...loginRequest,
  };

  const onLoad = async () => {
    if (currentAccount) {
      if (groupIds.includes('*') ) {
        setIsAuthorized(true);
      } else {
        const idTokenClaims = currentAccount.idTokenClaims;

        if (idTokenClaims !== undefined && idTokenClaims['groups']) {
          const userGroups = idTokenClaims['groups'];
          let intersection = groupIds.filter((group: string) => (userGroups as string[])?.includes(group));
    
          if (intersection.length > 0) {
            setIsAuthorized(true);
          }
        }
      }
    }
  };

  useEffect(() => {
    onLoad();
  }, [instance, currentAccount]);

  return (
    <MsalAuthenticationTemplate 
      interactionType={InteractionType.None} 
      authenticationRequest={authRequest}
    >
      {isAuthorized ? (
        props.children
      ) : (
        <div className={styles.authorizedBlock}>
          <h3>
            You are unauthorized to view this content.
            <SignOutButton />
          </h3>
        </div>
      )}
    </MsalAuthenticationTemplate>
  );
};
