import * as React from "react"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { XIcon } from "lucide-react"

import { cn } from "@/lib/utils"

const ExternalInteractionContext = React.createContext(false);

function Dialog({
  allowExternalInteraction = false,
  ...props
}) {
  // Opt in only for widgets that mount outside Content: a modal Radix dialog
  // otherwise blocks their pointer events and pulls focus back to its inputs.
  return (
    <ExternalInteractionContext.Provider value={allowExternalInteraction}>
      <DialogPrimitive.Root
        data-slot="dialog"
        {...props}
        modal={allowExternalInteraction ? false : (props.modal ?? true)}
      />
    </ExternalInteractionContext.Provider>
  );
}

function DialogTrigger({
  ...props
}) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />;
}

function DialogPortal({
  ...props
}) {
  return <DialogPrimitive.Portal data-slot="dialog-portal" {...props} />;
}

function DialogClose({
  ...props
}) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />;
}

function DialogOverlay({
  className,
  ...props
}) {
  const allowExternalInteraction = React.useContext(ExternalInteractionContext);

  React.useEffect(() => {
    if (!allowExternalInteraction) return;
    // Radix omits both Overlay and its scroll lock in non-modal mode. Keep the
    // backdrop and scroll lock without blocking the external challenge iframe.
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = originalOverflow; };
  }, [allowExternalInteraction]);

  if (allowExternalInteraction) {
    return (
      <div
        data-slot="dialog-overlay"
        aria-hidden="true"
        className={cn("fixed inset-0 z-50 bg-black/50", className)}
        {...props}
      />
    );
  }

  return (
    <DialogPrimitive.Overlay
      data-slot="dialog-overlay"
      className={cn(
        "fixed inset-0 z-50 bg-black/50",
        className
      )}
      {...props} />
  );
}

/**
 * Dialog content container.
 *
 * @param {boolean} [dismissOnOverlayClick=true] - Close when clicking outside the dialog
 */
function DialogContent({
  className,
  children,
  dismissOnOverlayClick = true,
  onInteractOutside,
  ...props
}) {
  const handleInteractOutside = (event) => {
    if (!dismissOnOverlayClick) event.preventDefault();
    onInteractOutside?.(event);
  };

  return (
    <DialogPortal data-slot="dialog-portal">
      <DialogOverlay />
      <DialogPrimitive.Content
        data-slot="dialog-content"
        className={cn(
          "bg-background data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 fixed top-[50%] left-[50%] z-50 grid w-[calc(100vw-2rem)] min-w-0 max-w-[calc(100%-2rem)] max-h-[calc(100dvh-2rem)] overflow-x-hidden overflow-y-auto [overflow-wrap:anywhere] [&>*]:min-w-0 translate-x-[-50%] translate-y-[-50%] gap-4 rounded-lg border p-4 sm:p-6 shadow-lg duration-200 sm:max-w-lg",
          className
        )}
        onInteractOutside={handleInteractOutside}
        {...props}
      >
        {children}
        <DialogPrimitive.Close
          className="ring-offset-background focus:ring-ring data-[state=open]:bg-accent data-[state=open]:text-muted-foreground absolute top-4 right-4 rounded-xs opacity-70 transition-opacity hover:opacity-100 focus:ring-2 focus:ring-offset-2 focus:outline-hidden disabled:pointer-events-none [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4"
        >
          <XIcon />
          <span className="sr-only">Close</span>
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPortal>
  );
}

function DialogHeader({
  className,
  ...props
}) {
  return (
    <div
      data-slot="dialog-header"
      className={cn("flex min-w-0 shrink-0 flex-col gap-2 pr-6 text-center sm:text-left", className)}
      {...props} />
  );
}

function DialogFooter({
  className,
  ...props
}) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn("flex flex-col-reverse gap-2 sm:flex-row sm:justify-end", className)}
      {...props} />
  );
}

function DialogTitle({
  className,
  ...props
}) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn("text-lg leading-none font-semibold", className)}
      {...props} />
  );
}

function DialogDescription({
  className,
  ...props
}) {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      className={cn("text-muted-foreground text-sm", className)}
      {...props} />
  );
}

export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
}
