import { Button, Modal, Collapse, Row, Col } from "react-bootstrap";
import * as React from "react";
import ReactLoading from "react-loading";
import * as yup from "yup";

import { AuthDialog } from "../auth";
import { AccessStatus, InitialValues, Inputs, RemoteOutputs, Simulation } from "../types";
import { CheckboxWidget } from "./notify";
import { isEqual } from "lodash";
import { formikToJSON } from "../ParamTools";
import { Utils as SimUtils } from "./sim";
import { RolePerms } from "../roles";

export const ValidatingModal: React.FC<{ defaultShow?: boolean }> = ({ defaultShow = true }) => {
  const [show, setShow] = React.useState(defaultShow);

  return (
    <div>
      <Modal show={show} onHide={() => setShow(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Validating inputs...</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <div className="d-flex justify-content-center">
            <ReactLoading type="spokes" color="#28a745" />
          </div>
        </Modal.Body>
      </Modal>
    </div>
  );
};

const PricingInfoCollapse: React.FC<{ accessStatus: AccessStatus }> = ({ accessStatus }) => {
  const [collapseOpen, setCollapseOpen] = React.useState(false);

  return (
    <>
      <Button
        onClick={() => setCollapseOpen(!collapseOpen)}
        aria-controls="pricing-collapse-text"
        aria-expanded={collapseOpen}
        variant="link"
        style={{ verticalAlign: "baseline" }}
      >
        Detail
      </Button>
      <Collapse in={collapseOpen}>
        <div id="pricing-collapse-text">
          The models are offered for free, but you pay for the computational resources used to run
          them. The prices are equal to Google Cloud Platform compute pricing, subject to costing at
          least one penny for a single run.
          <ul>
            <li>
              The price per hour of a server running this model is: ${`${accessStatus.server_cost}`}
              /hour.
            </li>
            <li>
              The expected time required for a single run of this model is:{" "}
              {`${accessStatus.exp_time}`} seconds.
            </li>
          </ul>
        </div>
      </Collapse>
    </>
  );
};

const RequirePmtDialog: React.FC<{
  accessStatus: AccessStatus;
  show: boolean;
  setShow?: React.Dispatch<any>;
  handleSubmit: () => void;
}> = ({ accessStatus, show, setShow, handleSubmit }) => {
  const handleCloseWithRedirect = (e, redirectLink) => {
    e.preventDefault();
    setShow(false);
    window.location.href = redirectLink;
  };
  return (
    <Modal show={show} onHide={() => setShow(false)}>
      <Modal.Header closeButton>
        <Modal.Title>Add a payment method</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        You must submit a payment method to run paid simulations.
        <PricingInfoCollapse accessStatus={accessStatus} />
      </Modal.Body>
      <Modal.Footer>
        <Button variant="outline-secondary" onClick={() => setShow(false)}>
          Close
        </Button>
        <Button
          variant="success"
          onClick={e =>
            handleCloseWithRedirect(
              e,
              `/billing/update/?next=${window.location.pathname}?showRunModal=true`
            )
          }
        >
          <b>Add payment method</b>
        </Button>
      </Modal.Footer>
    </Modal>
  );
};

const RunDialog: React.FC<{
  accessStatus: AccessStatus;
  show: boolean;
  setShow?: React.Dispatch<any>;
  handleSubmit: () => void;
  setNotify: (notify: boolean) => void;
  notify: boolean;
  setIsPublic: (isPublic: boolean) => void;
  isPublic: boolean;
  sim: Simulation<RemoteOutputs>;
}> = ({
  accessStatus,
  show,
  setShow,
  handleSubmit,
  setNotify,
  notify,
  setIsPublic,
  isPublic,
  sim,
}) => {
  const handleCloseWithSubmit = () => {
    setShow(false);
    handleSubmit();
  };

  const flipPublic = (_isPublic: boolean) => setIsPublic(!_isPublic);

  const createsNewSim = SimUtils.submitWillCreateNewSim(sim);

  let remainingPrivateSims = 3;
  const projectLower = accessStatus.project.toLowerCase();
  if (projectLower in accessStatus.remaining_private_sims) {
    remainingPrivateSims = accessStatus.remaining_private_sims[projectLower];
  }

  const { protocol, host } = window.location;
  const simUrl = `${protocol}//${host}${sim.gui_url}`;

  let sponsorMessage;
  if (accessStatus.sponsor_message) {
    sponsorMessage = accessStatus.sponsor_message;
  }
  const { plan } = accessStatus;
  const isPrivateRateLimited = plan.name === "free" && remainingPrivateSims <= 0;
  if (isPrivateRateLimited && createsNewSim) {
    isPublic = true;
  } else if (!createsNewSim) {
    isPublic = sim.is_public;
  }
  let visabilitymsg;
  if (isPublic) {
    visabilitymsg = (
      <div>
        <p>
          Public <a href="/log/">log</a> entry:{" "}
          <strong className="font-weight-bold">
            {!!sim?.title ? sim.title : `New ${accessStatus.project}`}
          </strong>{" "}
          {accessStatus.username !== "anon" && (
            <span>
              by <strong className="font-weight-bold">{accessStatus.username}</strong>
            </span>
          )}
        </p>
        <p>Public url: {createsNewSim ? "Yes" : <a href={simUrl}>{simUrl}</a>}</p>
      </div>
    );
  } else {
    visabilitymsg = (
      <div>
        <p>
          Public <a href="/log/">log</a> entry: None
        </p>
        <p>Public url: None</p>
        {!createsNewSim && (
          <p>
            Private url: <a href={simUrl}>{simUrl}</a>
          </p>
        )}
      </div>
    );
  }
  let makePrivate;
  if (plan.name === "free") {
    makePrivate = (
      <span>
        Make private ({remainingPrivateSims} remaining this month
        {isPrivateRateLimited && (
          <span>
            .{" "}
            <a href={`/billing/upgrade/yearly/?next=${window.location.pathname}?showRunModal=true`}>
              Upgrade to Pro
            </a>
          </span>
        )}
        )
      </span>
    );
  } else {
    makePrivate = <span>Make private</span>;
  }

  let optInMsg;
  if (!isPublic && plan.name !== "free" && plan.cancel_at && plan.trial_end) {
    optInMsg = (
      <Row className="px-2 pt-2">
        <Col className="text-center">
          <div className="alert alert-primary" role="alert">
            <p>Your free C/S Pro trial ends on {plan.trial_end}.</p>
            <p>
              <Button
                variant="primary"
                href={`/billing/upgrade/monthly/aftertrial/?next=${window.location.pathname}?showRunModal=true`}
              >
                <strong>Upgrade to C/S Pro after trial</strong>
              </Button>
            </p>
          </div>
        </Col>
      </Row>
    );
  }

  let pricing;
  if (accessStatus.is_sponsored) {
    pricing = (
      <Modal.Body>
        {visabilitymsg}
        <p>
          Pricing: Sponsored by{" "}
          {sponsorMessage ? (
            <div dangerouslySetInnerHTML={{ __html: sponsorMessage }} />
          ) : (
            "an anonymous user."
          )}
        </p>
      </Modal.Body>
    );
  } else {
    pricing = (
      <Modal.Body>
        {visabilitymsg}
        <>
          <span>
            Pricing: ${`${accessStatus.exp_cost}`}
            <PricingInfoCollapse accessStatus={accessStatus} />
          </span>
        </>
      </Modal.Body>
    );
  }

  return (
    <Modal show={show} onHide={() => setShow(false)}>
      <Modal.Header closeButton>
        <Modal.Title>Create a new {isPublic ? "public" : "private"} simulation</Modal.Title>
      </Modal.Header>
      {optInMsg}
      {pricing}
      <Modal.Footer style={{ justifyContent: "none" }}>
        <Row className="align-items-center w-100 justify-content-between">
          <Col className="col-md-auto">
            <Row>
              <Col>
                <CheckboxWidget
                  setValue={flipPublic}
                  value={!isPublic}
                  message={makePrivate}
                  disabled={isPrivateRateLimited && isPublic}
                />
              </Col>
            </Row>
            <Row>
              <Col>
                <CheckboxWidget setValue={setNotify} value={notify} message="Email me when ready" />
              </Col>
            </Row>
          </Col>
          <Col className="col--md-auto">
            <Button
              className="mr-3"
              variant="success"
              onClick={handleCloseWithSubmit}
              type="submit"
            >
              <strong>Run</strong>
            </Button>
          </Col>
        </Row>
      </Modal.Footer>
    </Modal>
  );
};

const Dialog: React.FC<{
  accessStatus: AccessStatus;
  resetAccessStatus: () => void;
  show: boolean;
  setShow: React.Dispatch<any>;
  handleSubmit: () => void;
  setNotify: (notify: boolean) => void;
  notify: boolean;
  setIsPublic: (isPublic: boolean) => void;
  isPublic: boolean;
  sim: Simulation<RemoteOutputs>;
}> = ({
  accessStatus,
  resetAccessStatus,
  show,
  setShow,
  handleSubmit,
  setNotify,
  notify,
  setIsPublic,
  isPublic,
  sim,
}) => {
  // pass new show and setShow so main run dialog is not closed.
  const [authShow, setAuthShow] = React.useState(true);
  if (accessStatus.can_run) {
    return (
      <RunDialog
        accessStatus={accessStatus}
        show={show}
        setShow={setShow}
        handleSubmit={handleSubmit}
        setNotify={setNotify}
        notify={notify}
        setIsPublic={setIsPublic}
        isPublic={isPublic}
        sim={sim}
      />
    );
  } else if (accessStatus.user_status === "anon") {
    // only consider showing AuthDialog if the run dialog is shown.
    return (
      <AuthDialog
        show={show ? authShow : false}
        setShow={setAuthShow}
        initialAction="sign-up"
        resetAccessStatus={resetAccessStatus}
        message="You must be logged in to run simulations"
      />
    );
  } else if (accessStatus.user_status === "profile") {
    return (
      <RequirePmtDialog
        accessStatus={accessStatus}
        show={show}
        setShow={setShow}
        handleSubmit={handleSubmit}
      />
    );
  }
};

export const RunModal: React.FC<{
  showModal: boolean;
  setShowModal: (showModal: boolean) => void;
  action: "Run" | "Fork and Run";
  handleSubmit: () => void;
  accessStatus: AccessStatus;
  resetAccessStatus: () => void;
  setNotify: (notify: boolean) => void;
  notify: boolean;
  setIsPublic: (isPublic: boolean) => void;
  isPublic: boolean;
  persist: () => void;
  sim: Simulation<RemoteOutputs>;
}> = ({
  showModal,
  setShowModal,
  action,
  handleSubmit,
  accessStatus,
  resetAccessStatus,
  setNotify,
  notify,
  setIsPublic,
  isPublic,
  persist,
  sim,
}) => {
  let runbuttontext: string;
  if (!accessStatus.is_sponsored) {
    runbuttontext = `${action} ($${accessStatus.exp_cost})`;
  } else {
    runbuttontext = action;
  }

  return (
    <>
      <div className="card card-body card-outer">
        <Button
          variant="primary"
          onClick={() => {
            // Persist values when clicking run in case the user navigates away.
            persist();
            setShowModal(true);
          }}
          className="btn btn-block btn-success"
        >
          <b>{runbuttontext}</b>
        </Button>
      </div>
      <Dialog
        accessStatus={accessStatus}
        resetAccessStatus={resetAccessStatus}
        show={showModal}
        setShow={setShowModal}
        handleSubmit={handleSubmit}
        setNotify={setNotify}
        notify={notify}
        setIsPublic={setIsPublic}
        isPublic={isPublic}
        sim={sim}
      />
    </>
  );
};

export const AuthModal: React.FC<{ msg?: string }> = ({
  msg = "You must be logged in to run simulations",
}) => {
  const [show, setShow] = React.useState(true);

  const handleClose = () => setShow(false);
  const handleCloseWithRedirect = (e, redirectLink) => {
    e.preventDefault();
    setShow(false);
    window.location.replace(redirectLink);
  };
  return (
    <>
      <Modal show={show} onHide={handleClose}>
        <Modal.Header closeButton>
          <Modal.Title>Sign up</Modal.Title>
        </Modal.Header>
        <Modal.Body>{msg}</Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={handleClose}>
            Close
          </Button>
          <Button variant="secondary" onClick={e => handleCloseWithRedirect(e, "/users/login")}>
            <b>Sign in</b>
          </Button>
          <Button variant="success" onClick={e => handleCloseWithRedirect(e, "/users/signup")}>
            <b>Sign up</b>
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
};

export const UnsavedChangesModal: React.FC<{ handleClose: () => void }> = ({ handleClose }) => {
  const [show, setShow] = React.useState(true);
  const close = () => {
    setShow(false);
    handleClose();
  };

  return (
    <>
      <Modal show={show} onHide={close}>
        <Modal.Header closeButton>
          <Modal.Title>Unsaved Changes</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          You have unsaved changes in the inputs form. You must create a new simulation to get new
          outputs corresponding to these changes.
        </Modal.Body>
        <Modal.Footer>
          <Button variant="outline-primary" onClick={close}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
};

const PreviewComponent: React.FC<{
  values: InitialValues;
  schema: yup.Schema<any>;
  tbLabelSchema: yup.Schema<any>;
  model_parameters: Inputs["model_parameters"];
  label_to_extend: string;
  extend: boolean;
}> = ({ values, schema, tbLabelSchema, model_parameters, label_to_extend, extend }) => {
  const [preview, setPreview] = React.useState({});

  const [show, setShow] = React.useState(false);

  const parseValues = () => {
    try {
      return formikToJSON(values, schema, tbLabelSchema, extend, label_to_extend, model_parameters);
    } catch (error) {
      return ["Something went wrong while creating the preview.", ""];
    }
  };

  const refresh = () => {
    const [meta_parameters, model_parameters] = parseValues();
    setPreview({
      meta_parameters: meta_parameters,
      adjustment: model_parameters,
    });
  };
  const handleShow = show => {
    if (show) {
      refresh();
    }
    setShow(show);
  };
  return (
    <>
      <div className="card card-body card-outer">
        <Button
          variant="primary"
          onClick={() => handleShow(true)}
          className="btn btn-block btn-outline-primary"
        >
          Adjustment
        </Button>
      </div>
      <Modal show={show} onHide={() => handleShow(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Preview JSON</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <pre>
            <code>{JSON.stringify(preview, null, 4)}</code>
          </pre>
          <Button variant="outline-success" className="col-3" onClick={refresh}>
            Refresh
          </Button>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="outline-primary" onClick={() => handleShow(false)}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
};
export const PreviewModal = React.memo(PreviewComponent, (prevProps, nextProps) => {
  return isEqual(prevProps.values, nextProps.values);
});
